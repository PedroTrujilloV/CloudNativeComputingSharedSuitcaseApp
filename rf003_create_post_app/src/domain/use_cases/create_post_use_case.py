"""Core RF-003 orchestration: route find-or-create + post creation.

Flow (per ``docs/diagrams/rf003-sequence.puml``):
  1. Resolve the route by ``flightId`` (reuse it when it exists, discarding
     the submitted route field values; otherwise create it).
  2. Validate the post ``expireAt`` against now and the route's
     ``plannedStartDate``.
  3. Reject the request when the user already has a post for the route.
  4. Create the post and shape the documented 201 response.

Consistency (saga compensation, see ``docs/solution-patterns.md``):
  The flow performs two writes on two independently owned stores (Routes,
  Posts) with no distributed transaction. If the post stage fails with an
  *integration* error after a **new** route was created, the orchestrator
  runs the compensating action (delete the just-created route) so the
  system ends consistent: either both writes exist or neither does.
  Business rejections (412s) never trigger compensation: at that point the
  only write performed is the new route, which is a legitimate, reusable
  entity (the next request for the same ``flightId`` reuses it).
"""

import logging
from datetime import datetime, timezone

from domain.models.route import RouteInfo
from domain.models.schemas import RF003CreatePostRequest
from domain.ports.posts_port import PostsPort
from domain.ports.routes_port import RoutesPort
from domain.ports.user_validation_port import AuthenticatedUser
from errors import (
    DuplicatePostError,
    ExpireAtInvalidError,
    PostsServiceUnavailableError,
    RoutesServiceUnavailableError,
)

logger = logging.getLogger("rf003_create_post_app")


def _ensure_naive_utc(dt: datetime) -> datetime:
    """Normalize a datetime to naive UTC for safe comparisons."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class CreatePostUseCase:
    """Orchestrates route resolution and post creation for RF-003."""

    def __init__(self, routes: RoutesPort, posts: PostsPort) -> None:
        self._routes = routes
        self._posts = posts

    def execute(self, user: AuthenticatedUser, payload: RF003CreatePostRequest) -> dict:
        """Run the orchestration and return the documented 201 body.

        Raises:
            RoutesServiceUnavailableError / RouteDatesInvalidError: route
                stage failures (surfed as 503 / 412 by the router).
            ExpireAtInvalidError / DuplicatePostError: post-stage 412s.
            PostsServiceUnavailableError: post stage failure (503). When it
                is raised after a new route was created, the compensating
                route deletion has already been attempted (and logged).
        """
        route, route_created = self._resolve_route(payload)
        try:
            self._validate_expire_at(payload.expireAt, route.plannedStartDate)
            self._check_duplicate(route, user)
            created = self._posts.create_post(
                route_id=route.id, user_id=user.id, expire_at=payload.expireAt
            )
        except PostsServiceUnavailableError:
            # Integration failure mid-flow: compensate so no orphaned route
            # survives (see module docstring). Business rejections
            # (ExpireAtInvalidError / DuplicatePostError) are NOT
            # compensated — they pass through untouched.
            self._compensate_route(route, route_created, user, payload)
            raise
        return self._build_response(user, payload, route, created)

    def _resolve_route(self, payload: RF003CreatePostRequest) -> tuple[RouteInfo, bool]:
        """Find the route by flightId or create it with the submitted values.

        Returns the route plus a flag indicating whether it was created by
        this request (only such routes are eligible for compensation).
        """
        existing = self._routes.find_by_flight_id(payload.flightId)
        if existing is not None:
            # The submitted route field values are discarded; the existing
            # route is reused as-is.
            logger.info(
                "RF003: reusing existing route %s for flightId=%s",
                existing.id,
                payload.flightId,
            )
            return existing, False
        route = self._routes.create_route(
            flight_id=payload.flightId,
            source_airport_code=payload.origin.airportCode,
            source_country=payload.origin.country,
            destiny_airport_code=payload.destiny.airportCode,
            destiny_country=payload.destiny.country,
            bag_cost=payload.bagCost,
            planned_start_date=payload.plannedStartDate,
            planned_end_date=payload.plannedEndDate,
        )
        logger.info(
            "RF003: created new route %s for flightId=%s",
            route.id,
            payload.flightId,
        )
        return route, True

    @staticmethod
    def _validate_expire_at(expire_at: datetime, planned_start: datetime) -> None:
        """Enforce ``now < expireAt <= plannedStartDate``."""
        now = _ensure_naive_utc(datetime.now(timezone.utc))
        expire = _ensure_naive_utc(expire_at)
        start = _ensure_naive_utc(planned_start)
        if expire <= now or expire > start:
            raise ExpireAtInvalidError("La fecha expiración no es válida")

    def _check_duplicate(self, route: RouteInfo, user: AuthenticatedUser) -> None:
        """Reject when the user already has a post for this route."""
        # The Posts service is the single source of truth for post data;
        # the orchestrator only asks whether a post already exists.
        if self._posts.has_post_for_route_and_owner(route.id, user.id):
            raise DuplicatePostError(
                "El usuario ya tiene una publicación para la misma fecha"
            )

    def _compensate_route(
        self,
        route: RouteInfo,
        route_created: bool,
        user: AuthenticatedUser,
        payload: RF003CreatePostRequest,
    ) -> None:
        """Compensate a partial failure (post creation failed with 503).

        Only a route *created by this request* is deleted: a pre-existing
        route is shared state that must survive the failed post attempt.
        A compensation failure is logged (the Routes service is down too)
        and swallowed — the original 503 is what the client receives.
        """
        if not route_created:
            logger.info(
                "RF003: post creation failed for user=%s flightId=%s; "
                "route %s pre-existed, nothing to compensate",
                user.id,
                payload.flightId,
                route.id,
            )
            return
        logger.warning(
            "RF003: post creation failed for user=%s flightId=%s; "
            "compensating by deleting newly created route %s",
            user.id,
            payload.flightId,
            route.id,
        )
        try:
            self._routes.delete_route(route.id)
        except RoutesServiceUnavailableError:
            logger.error(
                "RF003: compensation FAILED for route %s (flightId=%s): "
                "the Routes service is unreachable; an orphaned route may "
                "remain until the service recovers (it is safe to reuse: "
                "the next request for the same flightId will find it)",
                route.id,
                payload.flightId,
            )
        else:
            logger.info("RF003: compensation succeeded, route %s deleted", route.id)

    def _build_response(
        self,
        user: AuthenticatedUser,
        payload: RF003CreatePostRequest,
        route: RouteInfo,
        created,
    ) -> dict:
        """Shape the documented 201 body (``msg`` is a sibling of ``data``)."""
        return {
            "data": {
                "id": created.id,
                "userId": user.id,
                "createdAt": created.createdAt.isoformat(),
                "expireAt": payload.expireAt.isoformat(),
                "route": {
                    "id": route.id,
                    "createdAt": (
                        route.createdAt.isoformat() if route.createdAt else None
                    ),
                },
            },
            "msg": "Publicación creada exitosamente.",
        }
