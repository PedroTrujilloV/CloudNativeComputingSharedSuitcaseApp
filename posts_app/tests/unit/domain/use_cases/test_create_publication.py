"""
Unit tests for CreatePublicationUseCase.
"""
from datetime import datetime, timedelta

import pytest

from domain.use_cases.create_publication import CreatePublicationUseCase
from adapters.database.repository import PublicationRepository


class TestCreatePublicationUseCase:
    """Test suite for CreatePublicationUseCase."""

    @pytest.fixture
    def repository(self):
        """Provide a repository instance."""
        return PublicationRepository()

    @pytest.fixture
    def use_case(self, repository):
        """Provide use case instance."""
        return CreatePublicationUseCase(repository)

    def test_create_publication_success(self, use_case):
        """Test successful publication creation."""
        route_id = "route-123"
        user_id = "user-456"
        expire_at = datetime.utcnow() + timedelta(hours=1)

        publication = use_case.execute(route_id, user_id, expire_at)

        assert publication.id is not None
        assert publication.route_id == route_id
        assert publication.user_id == user_id
        assert publication.expire_at == expire_at
        assert publication.created_at is not None

    def test_create_publication_expire_at_in_past_raises_error(self, use_case):
        """Test that past expireAt raises ValueError."""
        route_id = "route-123"
        user_id = "user-456"
        expire_at = datetime.utcnow() - timedelta(hours=1)

        with pytest.raises(ValueError, match="must be in the future"):
            use_case.execute(route_id, user_id, expire_at)

    def test_create_publication_expire_at_now_raises_error(self, use_case):
        """Test that current time expireAt raises ValueError."""
        route_id = "route-123"
        user_id = "user-456"
        expire_at = datetime.utcnow()

        with pytest.raises(ValueError, match="must be in the future"):
            use_case.execute(route_id, user_id, expire_at)

    def test_create_publication_persist_in_db(self, use_case, repository):
        """Test that created publication is persisted."""
        route_id = "route-123"
        user_id = "user-456"
        expire_at = datetime.utcnow() + timedelta(hours=1)

        publication = use_case.execute(route_id, user_id, expire_at)
        retrieved = repository.get_by_id(publication.id)

        assert retrieved is not None
        assert retrieved.id == publication.id
        assert retrieved.route_id == route_id
