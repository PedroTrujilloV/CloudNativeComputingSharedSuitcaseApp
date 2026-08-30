"""
Publication Domain Model (Value Object).
Represents the business entity for a publication.
"""
from datetime import datetime
from typing import Optional
import uuid


class Publication:
    """
    Publication domain model.
    Represents a user's posting about available luggage space on a route.
    """

    def __init__(
        self,
        route_id: str,
        user_id: str,
        expire_at: datetime,
        id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        """
        Initialize Publication.

        Args:
            route_id: ID of the route
            user_id: ID of the user (owner)
            expire_at: Expiration datetime (must be in future)
            id: Publication ID (generated if not provided)
            created_at: Creation datetime (set to now if not provided)

        Raises:
            ValueError: If expire_at is not in the future
        """
        if expire_at <= datetime.utcnow():
            raise ValueError("expireAt must be in the future")

        self.id = id or str(uuid.uuid4())
        self.route_id = route_id
        self.user_id = user_id
        self.expire_at = expire_at
        self.created_at = created_at or datetime.utcnow()

    def __repr__(self) -> str:
        return (
            f"<Publication(id={self.id}, route_id={self.route_id}, "
            f"user_id={self.user_id}, expire_at={self.expire_at})>"
        )
