from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for Scores persistence."""


class ScoreModel(Base):
    """ORM mapping for the Utilidad (Score) entity.

    Persists a score value per offer so it can be retrieved later even if it
    changes over time (the document mandates a stateful, not calculate-only,
    component). A missing/undefined score for an offer is represented by the
    absence of a row, which callers treat as ``score: null``.
    """

    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    offerId: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
