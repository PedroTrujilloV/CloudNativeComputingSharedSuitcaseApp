import uuid
from datetime import datetime, timezone
from decimal import Decimal

from domain.models.offer import PackageSize
from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OfferModel(Base):
    __tablename__ = "offers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    postId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    userId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        String(140),
        nullable=False,
    )

    size: Mapped[PackageSize] = mapped_column(
        SQLEnum(PackageSize),
        nullable=False,
    )

    fragile: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    offer: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
