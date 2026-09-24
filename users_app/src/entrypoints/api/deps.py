from collections.abc import Generator

from sqlalchemy.orm import Session

from adapters.database.connection import build_session_factory
from adapters.database.user_repository_adapter import SQLAlchemyUserRepositoryAdapter
from adapters.truenative.verification_adapter import TrueNativeVerificationAdapter
from domain.ports.truenative_port import TrueNativeVerificationPort
from domain.ports.user_repository_port import UserRepositoryPort
from domain.use_cases.authenticate_user_use_case import AuthenticateUserUseCase
from domain.use_cases.base_use_case import BaseUseCase
from domain.use_cases.count_users_use_case import CountUsersUseCase
from domain.use_cases.create_user_use_case import CreateUserUseCase
from domain.use_cases.get_current_user_use_case import GetCurrentUserUseCase
from domain.use_cases.reset_users_use_case import ResetUsersUseCase
from domain.use_cases.update_user_use_case import UpdateUserUseCase


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session and close it afterwards."""
    session_factory = build_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_user_repository(session: Session) -> UserRepositoryPort:
    """Build the SQLAlchemy user repository."""
    return SQLAlchemyUserRepositoryAdapter(session)


def get_truenative_verification_provider() -> TrueNativeVerificationPort:
    """Build the TrueNative verification provider."""
    return TrueNativeVerificationAdapter()


def get_create_user_use_case(session: Session) -> BaseUseCase:
    """Build the create-user use case."""
    return CreateUserUseCase(
        get_user_repository(session),
        get_truenative_verification_provider(),
    )


def get_authenticate_user_use_case(session: Session) -> BaseUseCase:
    """Build the authenticate-user use case."""
    return AuthenticateUserUseCase(get_user_repository(session))


def get_current_user_use_case(session: Session) -> BaseUseCase:
    """Build the get-current-user use case."""
    return GetCurrentUserUseCase(get_user_repository(session))


def get_update_user_use_case(session: Session) -> BaseUseCase:
    """Build the update-user use case."""
    return UpdateUserUseCase(get_user_repository(session))


def get_count_users_use_case(session: Session) -> BaseUseCase:
    """Build the count-users use case."""
    return CountUsersUseCase(get_user_repository(session))


def get_reset_users_use_case(session: Session) -> BaseUseCase:
    """Build the reset-users use case."""
    return ResetUsersUseCase(get_user_repository(session))
