"""
Unit tests for PublicationRepository.
Tests CRUD operations and filtering logic.
"""
from datetime import datetime, timedelta
import pytest

from adapters.database.repository import PublicationRepository


@pytest.fixture
def repository():
    """Provide a repository instance with fresh database."""
    repo = PublicationRepository()
    repo.delete_all()
    yield repo
    repo.delete_all()


class TestCreatePublication:
    """Tests for publication creation."""

    def test_create_publication_success(self, repository):
        """Test successful publication creation."""
        future_time = datetime.utcnow() + timedelta(hours=1)

        publication = repository.create(
            route_id="AA001",
            user_id="user-123",
            expire_at=future_time,
        )

        assert publication.id is not None
        assert publication.route_id == "AA001"
        assert publication.user_id == "user-123"
        assert publication.expire_at == future_time
        assert publication.created_at is not None

    def test_create_publication_expire_at_in_past_fails(self, repository):
        """Test that creation fails if expire_at is in the past."""
        past_time = datetime.utcnow() - timedelta(hours=1)

        with pytest.raises(ValueError, match="expireAt must be in the future"):
            repository.create(
                route_id="AA001",
                user_id="user-123",
                expire_at=past_time,
            )

    def test_create_publication_expire_at_now_fails(self, repository):
        """Test that creation fails if expire_at is now."""
        now = datetime.utcnow()

        with pytest.raises(ValueError, match="expireAt must be in the future"):
            repository.create(
                route_id="AA001",
                user_id="user-123",
                expire_at=now,
            )


class TestGetPublication:
    """Tests for retrieving publications."""

    def test_get_by_id_success(self, repository):
        """Test retrieving publication by ID."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        created = repository.create(
            route_id="AA001",
            user_id="user-123",
            expire_at=future_time,
        )

        retrieved = repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.route_id == "AA001"

    def test_get_by_id_not_found(self, repository):
        """Test retrieving non-existent publication returns None."""
        result = repository.get_by_id("non-existent-id")

        assert result is None


class TestListPublications:
    """Tests for listing publications with filters."""

    def test_list_all_publications(self, repository):
        """Test listing all publications without filters."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        repository.create("AA001", "user-1", future_time)
        repository.create("BB002", "user-2", future_time)

        publications = repository.list()

        assert len(publications) == 2

    def test_list_filter_by_route_id(self, repository):
        """Test filtering publications by route ID."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        repository.create("AA001", "user-1", future_time)
        repository.create("BB002", "user-2", future_time)

        publications = repository.list(route_id="AA001")

        assert len(publications) == 1
        assert publications[0].route_id == "AA001"

    def test_list_filter_by_user_id(self, repository):
        """Test filtering publications by user ID."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        repository.create("AA001", "user-1", future_time)
        repository.create("AA001", "user-2", future_time)

        publications = repository.list(user_id="user-1")

        assert len(publications) == 1
        assert publications[0].user_id == "user-1"

    def test_list_filter_by_expire_status_expired(self, repository):
        """Test filtering by expired status."""
        past_time = datetime.utcnow() - timedelta(hours=1)
        future_time = datetime.utcnow() + timedelta(hours=1)

        pub1 = repository.create("AA001", "user-1", future_time)
        session = repository.SessionLocal()
        session.delete(session.merge(pub1))
        from adapters.database.models import Publication
        p = Publication(route_id="AA001", user_id="user-1", expire_at=past_time)
        session.add(p)
        session.commit()
        session.close()

        repository.create("BB002", "user-2", future_time)

        publications = repository.list(expire_status="expired")

        assert len(publications) == 1
        assert publications[0].route_id == "AA001"

    def test_list_filter_by_expire_status_not_expired(self, repository):
        """Test filtering by not expired status."""
        past_time = datetime.utcnow() - timedelta(hours=1)
        future_time = datetime.utcnow() + timedelta(hours=1)

        pub1 = repository.create("AA001", "user-1", future_time)
        session = repository.SessionLocal()
        session.delete(session.merge(pub1))
        from adapters.database.models import Publication
        p = Publication(route_id="AA001", user_id="user-1", expire_at=past_time)
        session.add(p)
        session.commit()
        session.close()

        repository.create("BB002", "user-2", future_time)

        publications = repository.list(expire_status="not_expired")

        assert len(publications) == 1
        assert publications[0].route_id == "BB002"

    def test_list_filter_combined_and_semantics(self, repository):
        """Test combined filters use AND semantics."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        repository.create("AA001", "user-1", future_time)
        repository.create("AA001", "user-2", future_time)
        repository.create("BB002", "user-1", future_time)

        publications = repository.list(route_id="AA001", user_id="user-1")

        assert len(publications) == 1
        assert publications[0].route_id == "AA001"
        assert publications[0].user_id == "user-1"


class TestDeletePublication:
    """Tests for deleting publications."""

    def test_delete_publication_success(self, repository):
        """Test successful publication deletion."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        created = repository.create("AA001", "user-1", future_time)

        result = repository.delete(created.id)

        assert result is True
        assert repository.get_by_id(created.id) is None

    def test_delete_publication_not_found(self, repository):
        """Test deleting non-existent publication returns False."""
        result = repository.delete("non-existent-id")

        assert result is False


class TestCountPublications:
    """Tests for counting publications."""

    def test_count_empty(self, repository):
        """Test count on empty database."""
        count = repository.count()

        assert count == 0

    def test_count_publications(self, repository):
        """Test counting multiple publications."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        repository.create("AA001", "user-1", future_time)
        repository.create("BB002", "user-2", future_time)

        count = repository.count()

        assert count == 2


class TestDeleteAll:
    """Tests for deleting all publications."""

    def test_delete_all_publications(self, repository):
        """Test deleting all publications."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        repository.create("AA001", "user-1", future_time)
        repository.create("BB002", "user-2", future_time)

        count = repository.delete_all()

        assert count == 2
        assert repository.count() == 0


class TestListPublicationsEdgeCases:
    """Additional tests for edge cases in listing."""

    def test_list_empty_database(self, repository):
        """Test listing from empty database."""
        publications = repository.list()
        assert publications == []

    def test_list_filter_nonexistent_route(self, repository):
        """Test filtering by non-existent route."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        repository.create("AA001", "user-1", future_time)

        publications = repository.list(route_id="NONEXISTENT")

        assert publications == []

    def test_list_filter_nonexistent_user(self, repository):
        """Test filtering by non-existent user."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        repository.create("AA001", "user-1", future_time)

        publications = repository.list(user_id="NONEXISTENT")

        assert publications == []


class TestRepositoryEdgeCases:
    """Additional edge case tests."""

    def test_create_preserves_exact_expire_at_time(self, repository):
        """Test that created publication has exact expire_at time."""
        specific_time = datetime.utcnow() + timedelta(hours=2, minutes=30, seconds=45)

        publication = repository.create("AA001", "user-1", specific_time)

        assert publication.expire_at == specific_time

    def test_get_by_id_after_delete_returns_none(self, repository):
        """Test getting a publication after deletion."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        created = repository.create("AA001", "user-1", future_time)

        repository.delete(created.id)

        assert repository.get_by_id(created.id) is None

    def test_count_after_operations(self, repository):
        """Test count is accurate after multiple operations."""
        future_time = datetime.utcnow() + timedelta(hours=1)

        assert repository.count() == 0

        repository.create("AA001", "user-1", future_time)
        assert repository.count() == 1

        repository.create("BB002", "user-2", future_time)
        assert repository.count() == 2

        repository.delete_all()
        assert repository.count() == 0
