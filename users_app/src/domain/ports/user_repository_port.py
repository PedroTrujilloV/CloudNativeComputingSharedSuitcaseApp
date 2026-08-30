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
    def count(self) -> int:
        """Count persisted users."""
        pass

    @abstractmethod
    def delete_all(self) -> None:
        """Delete all users (reset)."""
        pass
