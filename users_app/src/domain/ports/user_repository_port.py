from abc import ABC, abstractmethod

from domain.models.user import User


class UserRepositoryPort(ABC):
    """User repository interface."""

    @abstractmethod
    def create(self, user: User) -> User:
        """Persist a new user."""
        pass

    @abstractmethod
    def get_by_id(self, user_id: str) -> User | None:
        """Get user by id."""
        pass

    @abstractmethod
    def get_by_username(self, username: str) -> User | None:
        """Get user by username."""
        pass

    @abstractmethod
    def get_by_token(self, token: str) -> User | None:
        """Get user by opaque session token."""
        pass

    @abstractmethod
    def update(self, user: User) -> User:
        """Update an existing user."""
        pass

    @abstractmethod
    def set_ruv(self, user_id: str, ruv: str) -> User:
        """Store the RUV issued by TrueNative on the user record.

        Only the RUV column changes; the status and the updatedAt field are
        left untouched because storing the RUV is not a status change.
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """Count persisted users."""
        pass

    @abstractmethod
    def delete_all(self) -> None:
        """Delete all users (reset)."""
        pass
