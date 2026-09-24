"""Credit cards API router (creation, listing and utility flows, RF-006)."""

from domain.models.credit_card import format_iso_utc
from domain.models.verified_user import VerifiedUser
from domain.use_cases.base_use_case import BaseUseCase
from entrypoints.api.deps import (
    get_count_credit_cards_use_case,
    get_create_credit_card_use_case,
    get_current_user,
    get_list_credit_cards_use_case,
    get_reset_credit_cards_use_case,
)
from entrypoints.api.schemas.credit_card_schemas import (
    CountCreditCardsResponse,
    CreateCreditCardRequest,
    CreateCreditCardResponse,
    CreditCardResponse,
    ResetCreditCardsResponse,
)
from errors import (
    CardExpiredError,
    DuplicateCreditCardError,
    TrueNativeRegistrationError,
)
from fastapi import APIRouter, Depends
from fastapi.responses import Response

router = APIRouter(prefix="/credit-cards")


@router.post("", response_model=CreateCreditCardResponse, status_code=201)
@router.post(
    "/", response_model=CreateCreditCardResponse, status_code=201, include_in_schema=False
)
def create_credit_card(
    payload: CreateCreditCardRequest,
    current_user: VerifiedUser = Depends(get_current_user),
    use_case: BaseUseCase = Depends(get_create_credit_card_use_case),
):
    """Register a card: tokenize it, store it as POR_VERIFICAR, and answer.

    The synchronous path validates the caller, rejects expired and
    duplicated cards, tokenizes the card at TrueNative, persists the card
    as POR_VERIFICAR, and hands the slow verification off to the card
    worker through the queue. It answers with the card id, the owner id,
    and the creation date, in under five seconds.
    """
    try:
        card = use_case.execute(
            user_id=current_user.id,
            owner_email=current_user.email,
            card_number=payload.cardNumber,
            cvv=payload.cvv,
            expiration_date=payload.expirationDate,
            card_holder_name=payload.cardHolderName,
        )
    except CardExpiredError:
        return Response(status_code=412)
    except DuplicateCreditCardError:
        return Response(status_code=409)
    except TrueNativeRegistrationError:
        return Response(status_code=502)

    return CreateCreditCardResponse(
        id=card.id,
        userId=card.userId,
        createdAt=format_iso_utc(card.createdAt),
    )


@router.get("", response_model=list[CreditCardResponse])
@router.get(
    "/", response_model=list[CreditCardResponse], include_in_schema=False
)
def list_credit_cards(
    current_user: VerifiedUser = Depends(get_current_user),
    use_case: BaseUseCase = Depends(get_list_credit_cards_use_case),
):
    """List the caller's cards, user scoped (GET /credit-cards).

    The bearer token is validated against the users application (403
    without a token, 401 with an invalid or expired token), and the answer
    is the array of the cards the caller owns, each with the stored data
    (id, payment token, owner, last four digits, issuer, status) and the
    creation and update dates in ISO format. Cards of other users are
    never returned: the listing query is filtered by the caller id.
    """
    cards = use_case.execute(current_user.id)
    return [
        CreditCardResponse(
            id=card.id,
            token=card.token,
            userId=card.userId,
            lastFourDigits=card.lastFourDigits,
            issuer=card.issuer.value,
            status=card.status.value,
            createdAt=format_iso_utc(card.createdAt),
            updatedAt=format_iso_utc(card.updatedAt),
        )
        for card in cards
    ]


@router.get("/count", response_model=CountCreditCardsResponse)
@router.get("/count/", response_model=CountCreditCardsResponse, include_in_schema=False)
def count_credit_cards(
    use_case: BaseUseCase = Depends(get_count_credit_cards_use_case),
):
    """Count the stored cards (GET /credit-cards/count), no auth.

    The utility endpoints of the API specification require no bearer
    token. The answer is the current number of stored cards.
    """
    return CountCreditCardsResponse(count=use_case.execute())


@router.get("/ping")
@router.get("/ping/", include_in_schema=False)
def ping():
    """Liveness probe (GET /credit-cards/ping), no auth.

    The answer is the plain text ``pong`` (not a JSON string), the same
    contract as the TrueNative liveness probe.
    """
    return Response(content="pong", media_type="text/plain")


RESET_MESSAGE = "Todos los datos fueron eliminados"


@router.post("/reset", response_model=ResetCreditCardsResponse)
@router.post(
    "/reset/", response_model=ResetCreditCardsResponse, include_in_schema=False
)
def reset_credit_cards(
    use_case: BaseUseCase = Depends(get_reset_credit_cards_use_case),
):
    """Delete every stored card (POST /credit-cards/reset), no auth.

    The utility endpoints of the API specification require no bearer
    token. The answer carries the exact documented message string, which
    must not be translated.
    """
    use_case.execute()
    return ResetCreditCardsResponse(msg=RESET_MESSAGE)
