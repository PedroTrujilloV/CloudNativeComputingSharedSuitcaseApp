"""Dependency providers for the user verification callback receiver."""

from fastapi import Depends

from adapters.http.users_service_client import UsersServiceClient
from adapters.sns.sns_email_notification import SnsEmailNotification
from config import Settings
from domain.ports.email_notification_port import EmailNotificationPort
from domain.ports.user_update_port import UserUpdatePort
from domain.use_cases.process_verification_callback_use_case import (
    ProcessVerificationCallbackUseCase,
)


def get_users_service_client():
    """Yield a request scoped client for the Users service.

    A fresh ``httpx.Client`` is created per request and always closed, so
    no connection state leaks between requests.
    """
    client = UsersServiceClient()
    try:
        yield client
    finally:
        client.close()


def get_email_notification():
    """Yield a request scoped email notification publisher.

    The SNS client is created per request and always closed. The topic
    ARN, the region and the optional endpoint override come from the
    environment (the deploy pipeline resolves the topic ARN from the
    ``4_sns`` stack output before the manifest reaches the cluster).
    """
    publisher = SnsEmailNotification(
        topic_arn=Settings.user_verification_topic_arn,
        region=Settings.aws_region,
        endpoint_url=Settings.sns_endpoint_url or None,
    )
    try:
        yield publisher
    finally:
        publisher.close()


def get_process_verification_callback_use_case(
    user_update: UserUpdatePort = Depends(get_users_service_client),
    email_notification: EmailNotificationPort = Depends(get_email_notification),
) -> ProcessVerificationCallbackUseCase:
    """Build the callback processing use case with the shared secret token."""
    return ProcessVerificationCallbackUseCase(
        user_update=user_update,
        email_notification=email_notification,
        secret_token=Settings.secret_token,
    )
