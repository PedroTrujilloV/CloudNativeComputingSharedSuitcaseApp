"""
Create Publication Use Case.
Business logic for creating a publication.
"""
from datetime import datetime

from domain.models.publication import Publication
from domain.ports.publication_repository import PublicationRepository


class CreatePublicationUseCase:
    """
    Use case for creating a publication.
    Validates business rules and delegates persistence.
    """

    def __init__(self, repository: PublicationRepository):
        """
        Initialize use case with repository dependency.

        Args:
            repository: PublicationRepository implementation
        """
        self.repository = repository

    def execute(
        self,
        route_id: str,
        user_id: str,
        expire_at: datetime,
    ) -> Publication:
        """
        Execute the create publication use case.

        Args:
            route_id: ID of the route
            user_id: ID of the user
            expire_at: Expiration datetime (must be future)

        Returns:
            Created Publication object

        Raises:
            ValueError: If expireAt is not in the future
        """
        # Validate expire_at (raises ValueError if invalid)
        publication = Publication(
            route_id=route_id,
            user_id=user_id,
            expire_at=expire_at,
        )

        # Persist via repository
        return self.repository.create(
            route_id=publication.route_id,
            user_id=publication.user_id,
            expire_at=publication.expire_at,
        )
