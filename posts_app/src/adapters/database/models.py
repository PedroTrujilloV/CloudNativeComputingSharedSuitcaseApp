"""
SQLAlchemy ORM Models for Posts Service.
"""
from datetime import datetime
import uuid

from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Publication(Base):
    """
    Publication (Publicación) model representing a posting by a user
    about available space in their luggage for a specific route.
    """

    __tablename__ = "publications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    route_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    expire_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __init__(self, **kwargs):
        """Initialize with auto-generated id and created_at."""
        kwargs.setdefault("id", str(uuid.uuid4()))
        kwargs.setdefault("created_at", datetime.utcnow())
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<Publication(id={self.id}, route_id={self.route_id}, "
            f"user_id={self.user_id}, expire_at={self.expire_at})>"
        )
