"""FastAPI dependencies of the credit cards application."""

from collections.abc import Generator

from assembly import (
    build_card_event_publisher,
    build_credit_card_repository,
    build_true_native,
    build_user_verification,
)
from domain.models.verified_user import VerifiedUser
from domain.ports.card_event_publisher_port import CardEventPublisherPort
from domain.ports.credit_card_repository_port import CreditCardRepositoryPort
from domain.ports.true_native_port import TrueNativePort
from domain.ports.user_token_verification_port import UserTokenVerificationPort
from domain.use_cases.base_use_case import BaseUseCase
from domain.use_cases.count_credit_cards_use_case import CountCreditCardsUseCase
from domain.use_cases.create_credit_card_use_case import CreateCreditCardUseCase
from domain.use_cases.list_credit_cards_use_case import ListCreditCardsUseCase
from domain.use_cases.reset_credit_cards_use_case import ResetCreditCardsUseCase
from fastapi import Depends, Request

from errors import AuthTokenMissingError, InvalidTokenError


def get_user_verification() -> UserTokenVerificationPort:
    """Build the users application token verification adapter."""
    return build_user_verification()


def get_true_native() -> TrueNativePort:
    """Build the TrueNative tokenization adapter."""
    return build_true_native()


def get_credit_card_repository() -> Generator[CreditCardRepositoryPort, None, None]:
    """Build the DynamoDB credit card repository."""
    yield build_credit_card_repository()


def get_card_event_publisher() -> CardEventPublisherPort:
    """Build the SQS card verification event publisher."""
    return build_card_event_publisher()


def get_create_credit_card_use_case(
    true_native: TrueNativePort = Depends(get_true_native),
    credit_card_repository: CreditCardRepositoryPort = Depends(
        get_credit_card_repository
    ),
    card_event_publisher: CardEventPublisherPort = Depends(get_card_event_publisher),
) -> BaseUseCase:
    """Build the create credit card use case."""
    return CreateCreditCardUseCase(
        true_native=true_native,
        credit_card_repository=credit_card_repository,
        card_event_publisher=card_event_publisher,
    )


def get_list_credit_cards_use_case(
    credit_card_repository: CreditCardRepositoryPort = Depends(
        get_credit_card_repository
    ),
) -> BaseUseCase:
    """Build the list credit cards use case."""
    return ListCreditCardsUseCase(
        credit_card_repository=credit_card_repository,
    )


def get_count_credit_cards_use_case(
    credit_card_repository: CreditCardRepositoryPort = Depends(
        get_credit_card_repository
    ),
) -> BaseUseCase:
    """Build the count credit cards use case."""
    return CountCreditCardsUseCase(
        credit_card_repository=credit_card_repository,
    )


def get_reset_credit_cards_use_case(
    credit_card_repository: CreditCardRepositoryPort = Depends(
        get_credit_card_repository
    ),
) -> BaseUseCase:
    """Build the reset credit cards use case."""
    return ResetCreditCardsUseCase(
        credit_card_repository=credit_card_repository,
    )


def get_current_user(
    request: Request,
    user_verification: UserTokenVerificationPort = Depends(get_user_verification),
) -> VerifiedUser:
    """Resolve the caller from the Authorization header.

    The contract: a request without any bearer token answers 403, a
    present but unusable credential answers 401, and a valid token is
    verified against the users application (which also returns 401 for an
    invalid or expired token). The users application is never bypassed:
    this application has no access to its database. The answer carries
    the owner id and the owner email, the recipient of the card result
    notification.
    """
    header = request.headers.get("authorization")
    if header is None or not header.strip():
        raise AuthTokenMissingError()

    scheme, separator, token = header.partition(" ")
    if not separator or scheme.strip().lower() != "bearer":
        raise InvalidTokenError("The Authorization header must use Bearer")
    if not token.strip():
        raise AuthTokenMissingError()

    return user_verification.verify(token.strip())
