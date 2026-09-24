from abc import ABC, abstractmethod

from domain.models.verification_email import VerificationEmail


class EmailNotificationPort(ABC):
    """Port to notify the user of the identity verification result.

    The notification mechanism is the SNS email topic provisioned for
    RF-007 (the ``4_sns`` Terraform stack): the producer only publishes a
    message, and the topic delivers it by email to the address configured
    at deploy time (the ``EMAIL_TO_NOTIFY`` value), so no recipient
    address ever appears in this code.
    """

    @abstractmethod
    def notify_verification_result(self, email: VerificationEmail) -> bool:
        """Publish the verification result email.

        Returns ``True`` when the message was published and ``False`` when
        the notification mechanism is not configured (local runs without
        the topic ARN), in which case the skip is logged. Raises
        ``EmailNotificationError`` when the provider rejects the message.
        """
        pass
