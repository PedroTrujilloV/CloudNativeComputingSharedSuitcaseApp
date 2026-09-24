"""Synchronous creation flow of a credit card (POST /credit-cards).

The flow follows the RF-006 sequence view: the caller bearer token is
validated upstream (in the API layer, against the users application), and
this use case performs, in order, the expiration check, the duplicate
check, the TrueNative tokenization, the persistence as POR_VERIFICAR, and
the verification event publish. Every step is a plain synchronous call, so
the request answers within the 5 second budget without waiting for the
slow TrueNative verification, which is handed off to the card worker
through the queue.
"""

from datetime import datetime, timezone
from uuid import uuid4

from domain.models.credit_card import (
    CardIssuer,
    CardStatus,
    CreditCard,
    format_iso_utc,
)
from domain.ports.card_event_publisher_port import CardEventPublisherPort
from domain.ports.credit_card_repository_port import CreditCardRepositoryPort
from domain.ports.true_native_port import TrueNativePort
from domain.services.card_expiration import (
    expiration_year_and_month,
    is_expired,
)
from domain.services.issuer_detection import detect_issuer_from_bin
from domain.use_cases.base_use_case import BaseUseCase
from errors import (
    CardExpiredError,
    DuplicateCreditCardError,
    TrueNativeRegistrationError,
)


class CreateCreditCardUseCase(BaseUseCase):
    """Use case for creating a credit card from the synchronous flow."""

    def __init__(
        self,
        true_native: TrueNativePort,
        credit_card_repository: CreditCardRepositoryPort,
        card_event_publisher: CardEventPublisherPort,
    ):
        self.true_native = true_native
        self.credit_card_repository = credit_card_repository
        self.card_event_publisher = card_event_publisher

    def execute(
        self,
        user_id: str,
        card_number: str,
        cvv: str,
        expiration_date: str,
        card_holder_name: str,
        owner_email: str = "",
    ) -> CreditCard:
        """Create the card and return the stored entity.

        Raises:
            CardExpiredError: the presented card is already expired.
            DuplicateCreditCardError: the caller already stored this card.
            TrueNativeRegistrationError: TrueNative could not register the
                card or generate the token; nothing is persisted.
        """
        year, month = expiration_year_and_month(expiration_date)
        if is_expired(year, month, datetime.now(timezone.utc)):
            raise CardExpiredError()

        if self._caller_already_stored_the_card(user_id, card_number):
            raise DuplicateCreditCardError()

        registration = self.true_native.register_card(
            card_number=card_number,
            expiration_date=expiration_date,
            cvv=cvv,
            card_holder_name=card_holder_name,
            transaction_identifier=str(uuid4()),
        )

        now = datetime.now(timezone.utc)
        card = CreditCard(
            id=str(uuid4()),
            token=registration.token,
            userId=user_id,
            lastFourDigits=card_number[-4:],
            ruv=registration.ruv,
            issuer=self._resolve_issuer(registration.issuer, card_number),
            status=CardStatus.POR_VERIFICAR,
            createdAt=now,
            updatedAt=now,
        )
        stored = self.credit_card_repository.create(card)

        # The event carries the stored card data so the worker and the
        # eventual email notification are self contained, and the owner
        # email so the notification can be addressed to the card owner
        # (resolved through the users application API, never its
        # database). The publisher never raises for a hand off failure
        # (see the port contract).
        self.card_event_publisher.publish_verification_event(
            card_id=stored.id,
            ruv=stored.ruv,
            user_id=stored.userId,
            owner_email=owner_email,
            last_four_digits=stored.lastFourDigits,
            issuer=stored.issuer.value,
            status=stored.status.value,
            created_at=format_iso_utc(stored.createdAt),
        )
        return stored

    def _caller_already_stored_the_card(self, user_id: str, card_number: str) -> bool:
        """Check the caller's stored cards for the same card.

        The raw card number is never persisted, so the stored identity of a
        card is its last four digits: the same card submitted twice by the
        same user is detected by that field on the userId GSI.
        """
        last_four_digits = card_number[-4:]
        stored_cards = self.credit_card_repository.search(user_id=user_id)
        return any(
            stored.lastFourDigits == last_four_digits for stored in stored_cards
        )

    @staticmethod
    def _resolve_issuer(platform_issuer: str | None, card_number: str) -> CardIssuer:
        """Prefer the issuer returned by TrueNative, with BIN as fallback.

        The TrueNative platform derives the issuer from the card BIN and
        returns it in the registration response. When the response is
        missing it or carries a value outside the documented enum, the
        application falls back to its own BIN detection, which ends in
        ``UNKNOWN`` for unrecognized prefixes.
        """
        if platform_issuer:
            try:
                return CardIssuer(platform_issuer.strip().upper())
            except ValueError:
                pass
        return detect_issuer_from_bin(card_number)
