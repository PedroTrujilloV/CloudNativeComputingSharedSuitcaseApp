from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(DeclarativeBase):
    """SQLAlchemy declarative base class."""
    pass


class SQLAlchemyRouteModel(Base, MappedAsDataclass):
    """SQLAlchemy Route model representing a journey between airports."""

    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    flightId: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sourceAirportCode: Mapped[str] = mapped_column(String(3), nullable=False)
    sourceCountry: Mapped[str] = mapped_column(String(100), nullable=False)
    destinyAirportCode: Mapped[str] = mapped_column(String(3), nullable=False)
    destinyCountry: Mapped[str] = mapped_column(String(100), nullable=False)
    bagCost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plannedStartDate: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    plannedEndDate: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("flightId", name="uq_routes_flight_id"),
    )

    def to_route(self):
        """Convert SQLAlchemy model to domain model."""
        from domain.models.route import Route

        return Route.from_db({
            "id": self.id,
            "flightId": self.flightId,
            "sourceAirportCode": self.sourceAirportCode,
            "sourceCountry": self.sourceCountry,
            "destinyAirportCode": self.destinyAirportCode,
            "destinyCountry": self.destinyCountry,
            "bagCost": self.bagCost,
            "plannedStartDate": self.plannedStartDate,
            "plannedEndDate": self.plannedEndDate,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        })


# Re-export for convenience
RouteModel = SQLAlchemyRouteModel
