from abc import ABC, abstractmethod

from domain.models.updated_user_data import UpdatedUserData


class UserUpdatePort(ABC):
    """Port to update the user status in the Users service."""

    @abstractmethod
    def update_status(self, user_id: str, status: str) -> UpdatedUserData:
        """Update the user status through the Users service API.

        The status change also refreshes ``updatedAt`` on the user record,
        and the answer carries the updated user data (the source of the
        result email content). Raises ``UserNotFoundError`` when the user
        does not exist and ``UsersServiceUnavailableError`` when the
        service cannot be reached or answers an error.
        """
        pass
