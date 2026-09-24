import hashlib
import hmac
import logging
from dataclasses import dataclass

from domain.models.updated_user_data import UpdatedUserData
from domain.models.verification_callback import VerificationCallback
from domain.models.verification_email import VerificationEmail
from domain.ports.email_notification_port import EmailNotificationPort
from domain.ports.user_update_port import UserUpdatePort
from errors import (
    EmailNotificationError,
    UserNotFoundError,
    UsersServiceUnavailableError,
)

logger = logging.getLogger("user_verification_callback")

# Team decision documented in docs/rf007-sequence-view.md: the user is
# VERIFICADO only when the score is greater than 60; a score of 60 or lower
# is NO_VERIFICADO (the TrueNative callback condition).
SCORE_THRESHOLD = 60


@dataclass
class CallbackProcessingResult:
    """Outcome of one callback processing, used for logging and tests."""

    applied: bool
    reason: str
    target_status: str | None = None
    # Outcome of the result email for applied updates only: "sent",
    # "skipped" (notification mechanism not configured) or "failed"
    # (the provider rejected the message; the status change is kept).
    email_outcome: str | None = None


class ProcessVerificationCallbackUseCase:
    """Verify the TrueNative callback and apply the user status change.

    The signature is verified before any part of the payload is trusted,
    then the score is mapped to the user status with the team threshold.
    The update happens synchronously inside the request through the Users
    service API (the callback never touches the users database), the
    result email is published synchronously to the RF-007 SNS topic from
    the data the platform persists, and the endpoint answers HTTP 200 to
    TrueNative on receipt in every case.
    """

    def __init__(
        self,
        user_update: UserUpdatePort,
        email_notification: EmailNotificationPort,
        secret_token: str,
    ):
        self.user_update = user_update
        self.email_notification = email_notification
        self.secret_token = secret_token

    def execute(self, callback: VerificationCallback) -> CallbackProcessingResult:
        if not self._signature_is_valid(callback):
            logger.warning(
                "Discarding verification callback for RUV %s: the verifyToken "
                "does not match sha256(SECRET_TOKEN:RUV:SCORE); no status "
                "change is applied",
                callback.RUV,
            )
            return CallbackProcessingResult(applied=False, reason="signature_mismatch")

        target_status = self._status_for_score(callback.score)
        try:
            updated = self.user_update.update_status(
                callback.userIdentifier, target_status
            )
        except UserNotFoundError:
            logger.warning(
                "Verification callback for RUV %s: the Users service does not "
                "know user %s; the message is discarded",
                callback.RUV,
                callback.userIdentifier,
            )
            return CallbackProcessingResult(
                applied=False, reason="user_not_found", target_status=target_status
            )
        except UsersServiceUnavailableError as err:
            logger.error(
                "Verification callback for RUV %s: the Users service is "
                "unavailable (%s); the status change could not be applied",
                callback.RUV,
                err,
            )
            return CallbackProcessingResult(
                applied=False, reason="users_service_error", target_status=target_status
            )

        logger.info(
            "Verification callback for RUV %s applied: user %s is now %s " "(score %s)",
            callback.RUV,
            callback.userIdentifier,
            target_status,
            callback.score,
        )
        return CallbackProcessingResult(
            applied=True,
            reason="status_updated",
            target_status=target_status,
            email_outcome=self._notify_result(callback, target_status, updated),
        )

    def _signature_is_valid(self, callback: VerificationCallback) -> bool:
        """Verify ``verifyToken`` as ``sha256(f"{SECRET_TOKEN}:{RUV}:{SCORE}")``."""
        material = f"{self.secret_token}:{callback.RUV}:{callback.score}"
        expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
        received = callback.verifyToken
        if not received.isascii():
            return False
        return hmac.compare_digest(expected, received)

    @staticmethod
    def _status_for_score(score: int | float) -> str:
        """Map the score to the user status (threshold: strictly greater than 60)."""
        if score > SCORE_THRESHOLD:
            return "VERIFICADO"
        return "NO_VERIFICADO"

    def _notify_result(
        self,
        callback: VerificationCallback,
        target_status: str,
        updated: UpdatedUserData | None,
    ) -> str:
        """Publish the result email after the status update was applied.

        The content comes from the user record the platform persisted in
        the status update answer (with the callback payload values as the
        fallback), so the email states exactly what the platform stores.
        A notification failure never undoes the applied status change:
        the change is already persisted, and the endpoint must answer
        HTTP 200 to TrueNative in every case.
        """
        email = VerificationEmail(
            user_id=updated.id if updated and updated.id else callback.userIdentifier,
            status=updated.status if updated and updated.status else target_status,
            ruv=updated.ruv if updated and updated.ruv else callback.RUV,
            score=callback.score,
            username=updated.username if updated else None,
            email=updated.email if updated else None,
            dni=updated.dni if updated else None,
            full_name=updated.fullName if updated else None,
            phone_number=updated.phoneNumber if updated else None,
        )
        try:
            sent = self.email_notification.notify_verification_result(email)
        except EmailNotificationError as err:
            logger.error(
                "Email notification for RUV %s failed: %s; the status change "
                "is kept",
                callback.RUV,
                err,
            )
            return "failed"
        return "sent" if sent else "skipped"
