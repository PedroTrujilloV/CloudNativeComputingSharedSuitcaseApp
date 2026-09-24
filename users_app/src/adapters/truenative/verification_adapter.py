import logging

import httpx

from config import Settings
from domain.models.user import User
from domain.ports.truenative_port import TrueNativeVerificationPort
from errors import TrueNativeRequestError, TrueNativeUnreachableError

logger = logging.getLogger(__name__)

# The POST /native/verify endpoint only registers the verification request
# (the result arrives later through the webhook), so a bounded timeout keeps
# the user creation request from blocking on the external platform.
REQUEST_TIMEOUT_SECONDS = 10.0


class TrueNativeVerificationAdapter(TrueNativeVerificationPort):
    """Synchronous client for the TrueNative identity verification API."""

    def __init__(self, transport: httpx.BaseTransport | None = None):
        # A transport may be injected for unit testing (httpx.MockTransport);
        # in production the default network transport is used.
        self._transport = transport

    def request_verification(
        self,
        *,
        user: User,
        user_identifier: str,
        transaction_identifier: str,
    ) -> str:
        """Register the verification and return the RUV issued by TrueNative.

        Raises TrueNativeRequestError for HTTP error answers (400, 401, 403,
        409, or any other non 201 status) and TrueNativeUnreachableError when
        the platform cannot be reached or answers a malformed success body.
        """
        payload = {
            "user": self._build_user_payload(user),
            "userIdentifier": user_identifier,
            "transactionIdentifier": transaction_identifier,
            "userWebhook": Settings.user_webhook_url,
        }
        headers = {"Authorization": f"Bearer {Settings.truenative_secret_token}"}
        url = f"{Settings.truenative_base_url.rstrip('/')}/native/verify"

        with httpx.Client(transport=self._transport) as client:
            try:
                response = client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except httpx.HTTPError as exc:
                raise TrueNativeUnreachableError(
                    f"TrueNative could not be reached at {url}: {exc}"
                ) from exc

        if response.status_code == 201:
            return self._extract_ruv(response, transaction_identifier)

        detail = response.text or "no body"
        logger.warning(
            "TrueNative rejected verification request %s for user %s with "
            "status %s: %s",
            transaction_identifier,
            user_identifier,
            response.status_code,
            detail,
        )
        raise TrueNativeRequestError(response.status_code, detail)

    @staticmethod
    def _build_user_payload(user: User) -> dict:
        """Send as many user fields as are available.

        The more data is sent, the higher the verification success
        probability, so every optional field that has a value is included
        (empty fields are omitted).
        """
        payload = {"email": user.email}
        if user.dni:
            payload["dni"] = user.dni
        if user.fullName:
            payload["fullName"] = user.fullName
        if user.phoneNumber:
            payload["phone"] = user.phoneNumber
        return payload

    @staticmethod
    def _extract_ruv(response: httpx.Response, transaction_identifier: str) -> str:
        """Return the RUV from a 201 answer, or raise a malformed response error."""
        try:
            body = response.json()
        except ValueError as exc:
            raise TrueNativeUnreachableError(
                "TrueNative answered 201 with a non JSON body for verification "
                f"request {transaction_identifier}"
            ) from exc

        ruv = body.get("RUV") if isinstance(body, dict) else None
        if not ruv:
            raise TrueNativeUnreachableError(
                f"TrueNative answered 201 without a RUV for verification "
                f"request {transaction_identifier}"
            )
        return ruv
