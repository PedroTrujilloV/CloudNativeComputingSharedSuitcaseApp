"""
Repository layer for Publication persistence operations.
Implements CRUD operations and filtering logic.
"""
from datetime import datetime
from typing import List, Optional

from adapters.database.connection import get_engine, get_session_factory
from adapters.database.models import Publication


class PublicationRepository:
    """
    Repository for Publication entity persistence operations.
    Handles all database interactions for publications.
    """

    def __init__(self):
        """Bind the repository to the process-wide engine.

        The engine is shared so that every request sees the same data. With the
        default in-memory SQLite URL, a per-instance engine would give each
        repository its own empty database. Table creation belongs to the engine,
        not here: a repository is built inside every handler.
        """
        self.engine = get_engine()
        self.SessionLocal = get_session_factory()

    def create(
        self,
        route_id: str,
        user_id: str,
        expire_at: datetime,
    ) -> Publication:
        """
        Create a new publication.

        Args:
            route_id: ID of the route
            user_id: ID of the user creating the publication
            expire_at: Expiration datetime (must be in the future)

        Returns:
            Created Publication object

        Raises:
            ValueError: If expire_at is not in the future
        """
        if expire_at <= datetime.utcnow():
            raise ValueError("expireAt must be in the future")

        session = self.SessionLocal()
        try:
            publication = Publication(
                route_id=route_id,
                user_id=user_id,
                expire_at=expire_at,
            )
            session.add(publication)
            session.commit()
            session.refresh(publication)
            return publication
        finally:
            session.close()

    def get_by_id(self, publication_id: str) -> Optional[Publication]:
        """
        Get a publication by ID.

        Args:
            publication_id: UUID of the publication

        Returns:
            Publication object or None if not found
        """
        session = self.SessionLocal()
        try:
            return session.query(Publication).filter(
                Publication.id == publication_id
            ).first()
        finally:
            session.close()

    def list(
        self,
        route_id: Optional[str] = None,
        user_id: Optional[str] = None,
        expire_status: Optional[str] = None,
    ) -> List[Publication]:
        """
        List publications with optional filters (AND semantics).

        Args:
            route_id: Filter by route ID (optional)
            user_id: Filter by user ID (optional)
            expire_status: Filter by expiration status:
                          "expired" for expired publications
                          "not_expired" for active publications
                          None for all (optional)

        Returns:
            List of Publication objects matching filters
        """
        session = self.SessionLocal()
        try:
            query = session.query(Publication)

            if route_id:
                query = query.filter(Publication.route_id == route_id)

            if user_id:
                query = query.filter(Publication.user_id == user_id)

            if expire_status == "expired":
                query = query.filter(Publication.expire_at <= datetime.utcnow())
            elif expire_status == "not_expired":
                query = query.filter(Publication.expire_at > datetime.utcnow())

            return query.all()
        finally:
            session.close()

    def delete(self, publication_id: str) -> bool:
        """
        Delete a publication by ID.

        Args:
            publication_id: UUID of the publication

        Returns:
            True if deleted, False if not found
        """
        session = self.SessionLocal()
        try:
            publication = session.query(Publication).filter(
                Publication.id == publication_id
            ).first()

            if not publication:
                return False

            session.delete(publication)
            session.commit()
            return True
        finally:
            session.close()

    def count(self) -> int:
        """
        Count total publications in database.

        Returns:
            Total number of publications
        """
        session = self.SessionLocal()
        try:
            return session.query(Publication).count()
        finally:
            session.close()

    def delete_all(self) -> int:
        """
        Delete all publications (used for reset/testing).

        Returns:
            Number of publications deleted
        """
        session = self.SessionLocal()
        try:
            count = session.query(Publication).delete()
            session.commit()
            return count
        finally:
            session.close()
