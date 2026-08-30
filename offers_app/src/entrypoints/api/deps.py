from collections.abc import Generator

from adapters.database.connection import build_session_factory
from adapters.database.offer_repository_adapter import SQLAlchemyOfferRepositoryAdapter
from domain.ports.offer_repository_port import OfferRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from domain.use_cases.count_offers_use_case import CountOffersUseCase
from domain.use_cases.create_offer_use_case import CreateOfferUseCase
from domain.use_cases.delete_all_offers_use_case import DeleteAllOffersUseCase
from domain.use_cases.delete_offer_use_case import DeleteOfferUseCase
from domain.use_cases.get_offer_use_case import GetOfferUseCase
from domain.use_cases.list_offers_use_case import ListOffersUseCase
from sqlalchemy.orm import Session


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session and close it afterwards."""
    session_factory = build_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_offer_repository(session: Session) -> OfferRepositoryPort:
    """Build the SQLAlchemy offer repository."""
    return SQLAlchemyOfferRepositoryAdapter(session)


def get_create_offer_use_case(session: Session) -> BaseUseCase:
    """Build the create-offer use case."""
    return CreateOfferUseCase(get_offer_repository(session))


def get_delete_all_offers_use_case(session: Session) -> BaseUseCase:
    """Build the delete-all-offers use case."""
    return DeleteAllOffersUseCase(get_offer_repository(session))


def get_list_offers_use_case(session: Session) -> BaseUseCase:
    """Build the list-offers use case."""
    return ListOffersUseCase(get_offer_repository(session))


def get_get_offer_use_case(session: Session) -> BaseUseCase:
    """Build the get-offer use case."""
    return GetOfferUseCase(get_offer_repository(session))


def get_delete_offer_use_case(session: Session) -> BaseUseCase:
    """Build the delete-offer use case."""
    return DeleteOfferUseCase(get_offer_repository(session))


def get_count_offers_use_case(session: Session) -> BaseUseCase:
    """Build the count-offers use case."""
    return CountOffersUseCase(get_offer_repository(session))
