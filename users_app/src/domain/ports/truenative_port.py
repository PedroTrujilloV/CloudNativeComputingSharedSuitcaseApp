from abc import ABC, abstractmethod

from domain.models.user import User


class TrueNativeVerificationPort(ABC):
    """Identity verification provider interface (implemented by TrueNative)."""

    @abstractmethod
    def request_verification(
        self,
        *,
        user: User,
        user_identifier: str,
        transaction_identifier: str,
    ) -> str:
        """Register a verification request with the provider.

        Sends as many user fields as are available (email, dni, fullName,
        phone), the value that identifies the user in the local system, and
        a unique transaction identifier for traceability.

        Returns the unique verification record (RUV) issued by the provider.
        Raises a TrueNativeError subclass when the provider rejects the
        request (400, 401, 403, 409, or any other error status) or cannot be
        reached.
        """
        pass
