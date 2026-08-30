"""
Unit tests for Publication domain model validation.
Tests data integrity and business rules.
"""
from datetime import datetime, timedelta

from adapters.database.models import Publication


class TestPublicationModel:
    """Tests for Publication model."""

    def test_publication_creation_with_uuid(self):
        """Test creating publication with generated UUID."""
        future_time = datetime.utcnow() + timedelta(hours=1)

        pub = Publication(
            route_id="AA001",
            user_id="user-123",
            expire_at=future_time,
        )

        assert pub.id is not None
        assert len(pub.id) == 36
        assert pub.route_id == "AA001"
        assert pub.user_id == "user-123"

    def test_publication_created_at_auto_set(self):
        """Test that created_at is automatically set."""
        future_time = datetime.utcnow() + timedelta(hours=1)

        pub = Publication(
            route_id="AA001",
            user_id="user-123",
            expire_at=future_time,
        )

        assert pub.created_at is not None
        assert isinstance(pub.created_at, datetime)

    def test_publication_repr(self):
        """Test publication string representation."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        pub = Publication(
            id="test-id",
            route_id="AA001",
            user_id="user-123",
            expire_at=future_time,
        )

        repr_str = repr(pub)

        assert "Publication" in repr_str
        assert "AA001" in repr_str
        assert "user-123" in repr_str
