"""HTTP adapter for the TrueNative card tokenization platform."""

import json
from collections.abc import Callable

from httpx2 import Client, HTTPError

from config import Settings
from domain.ports.true_native_port import (
    TrueNativePort,
    TrueNativeRegistration,
)
from domain.services.card_expiration import expiration_year_and_month
from errors import TrueNativeRegistrationError


class HttpTrueNativeAdapter(TrueNativePort):
    """Registers cards at TrueNative through its REST API.

    The raw card number and the CVV travel only inside this request: the
    platform tokenizes them and returns the RUV, the platform token, and
    the issuer derived from the card BIN. Every answer that is not a
    successful registration (bad or missing secret token, malformed
    request, a verification already in progress, or any other failure)
    surfaces as ``TrueNativeRegistrationError``, and the caller persists
    nothing in that case.
    """

    def __init__(
        self,
        base_url: str | None = None,
        secret_token: str | None = None,
        timeout: float | None = None,
        client_factory: Callable[[], Client] | None = None,
    ):
        self.base_url = (base_url or Settings.truenative_url).rstrip("/")
        self.secret_token = secret_token if secret_token is not None else (
            Settings.truenative_secret_token
        )
        self.timeout = timeout if timeout is not None else Settings.http_timeout_seconds
        self.client_factory = client_factory

    def _new_client(self) -> Client:
        """Create the HTTP client used for the call (test seam included)."""
        if self.client_factory is not None:
            return self.client_factory()
        return Client(timeout=self.timeout)

    def register_card(
        self,
        card_number: str,
        expiration_date: str,
        cvv: str,
        card_holder_name: str,
        transaction_identifier: str,
    ) -> TrueNativeRegistration:
        """Send the card object to ``POST /native/cards`` and read the result."""
        year, month = expiration_year_and_month(expiration_date)
        payload = {
            "card": {
                "cardNumber": card_number,
                "expirationDate": f"{month:02d}/{year:04d}",
                "cvv": cvv,
                "cardHolderName": card_holder_name,
            },
            "transactionIdentifier": transaction_identifier,
        }
        try:
            with self._new_client() as client:
                response = client.post(
                    f"{self.base_url}/native/cards",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.secret_token}"},
                )
        except HTTPError as exc:
            raise TrueNativeRegistrationError(
                "TrueNative could not be reached"
            ) from exc

        if response.status_code not in (200, 201):
            raise TrueNativeRegistrationError(
                f"TrueNative answered with status {response.status_code}"
            )
        return self._parse_registration(response.text, transaction_identifier)

    @staticmethod
    def _parse_registration(
        body: str, transaction_identifier: str
    ) -> TrueNativeRegistration:
        """Extract the RUV, the token, and the issuer from the platform answer."""
        try:
            data = json.loads(body)
        except ValueError:
            raise TrueNativeRegistrationError(
                "TrueNative answered with an unexpected body"
            ) from None
        if not isinstance(data, dict):
            raise TrueNativeRegistrationError(
                "TrueNative answered with an unexpected body"
            )
        ruv = data.get("RUV")
        token = data.get("token")
        if not ruv or not token:
            raise TrueNativeRegistrationError(
                "TrueNative did not return the RUV or the card token"
            )
        issuer = data.get("issuer")
        return TrueNativeRegistration(
            ruv=str(ruv),
            token=str(token),
            issuer=str(issuer) if issuer else None,
            transaction_identifier=transaction_identifier,
        )
