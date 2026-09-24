"""Port for the TrueNative card tokenization platform.

TrueNative is the external platform that tokenizes the raw card data. The
application sends the card object together with a unique transaction
identifier and receives back the RUV, the platform token, and the issuer
derived from the card BIN. The raw card number and CVV live only in this
call and are never persisted.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TrueNativeRegistration:
    """Result of a successful ``POST /native/cards`` call."""

    ruv: str
    token: str
    issuer: str | None
    transaction_identifier: str


class TrueNativePort(ABC):
    """Driven interface for registering a card at TrueNative."""

    @abstractmethod
    def register_card(
        self,
        card_number: str,
        expiration_date: str,
        cvv: str,
        card_holder_name: str,
        transaction_identifier: str,
    ) -> TrueNativeRegistration:
        """Request the card token at TrueNative.

        The call is authenticated with the platform secret token and must
        answer within the request budget of the synchronous creation flow.

        Raises:
            TrueNativeRegistrationError: the platform cannot register the
                card or generate the token (bad secret token, malformed
                request, verification already in progress, or any other
                failure). Nothing must be persisted in that case.
        """
