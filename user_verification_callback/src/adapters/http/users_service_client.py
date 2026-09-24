"""HTTP client adapter for the Users service."""

import httpx

from config import Settings
from domain.models.updated_user_data import UpdatedUserData
from domain.ports.user_update_port import UserUpdatePort
from errors import UserNotFoundError, UsersServiceUnavailableError


class UsersServiceClient(UserUpdatePort):
    """Update the user status through the Users service API.

    The Users service (``PATCH /users/{id}``) already implements the exact
    contract the callback needs: it accepts a partial update with the
    ``status`` field, refreshes ``updatedAt`` on the change, answers
    ``404`` for an unknown user, and returns the updated user record so
    the callback can build the result email from the data the platform
    persists. The callback never accesses the users database directly, so
    the data ownership rule is preserved.
    """

    def __init__(self, client: httpx.Client | None = None):
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=Settings.users_service_url, timeout=Settings.http_timeout
        )

    def update_status(self, user_id: str, status: str) -> UpdatedUserData:
        """Send ``PATCH /users/{user_id}`` with the new status.

        Returns the updated user data from the response (the source of
        the result email content); an empty value is returned when the
        response carries no user block.
        """
        try:
            response = self._client.patch(f"/users/{user_id}", json={"status": status})
        except httpx.HTTPError as exc:
            raise UsersServiceUnavailableError(
                "The Users service is temporarily unavailable"
            ) from exc

        if response.status_code == 200:
            return self._updated_user_data(response)
        if response.status_code == 404:
            raise UserNotFoundError(f"User with id {user_id} not found")
        raise UsersServiceUnavailableError(
            "The Users service is temporarily unavailable"
        )

    @staticmethod
    def _updated_user_data(response: httpx.Response) -> UpdatedUserData:
        """Parse the updated user from the response, tolerating its absence."""
        try:
            body = response.json()
        except ValueError:
            return UpdatedUserData()
        user = body.get("user") if isinstance(body, dict) else None
        if not isinstance(user, dict):
            return UpdatedUserData()
        known = UpdatedUserData.model_fields.keys()
        return UpdatedUserData(
            **{key: value for key, value in user.items() if key in known}
        )

    def close(self) -> None:
        """Close the underlying HTTP client when we own it."""
        if self._owns_client:
            self._client.close()
