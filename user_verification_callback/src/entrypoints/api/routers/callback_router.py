"""Callback router: the public TrueNative verification webhook.

The endpoint is public by design (TrueNative has no authorization
mechanism for callbacks): the SHA256 signature check is its only
protection. It always answers HTTP 200 on a well formed receipt, as the
TrueNative contract requires, whatever the processing outcome is.
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response

from domain.models.verification_callback import VerificationCallback
from domain.use_cases.process_verification_callback_use_case import (
    ProcessVerificationCallbackUseCase,
)
from entrypoints.api.deps import get_process_verification_callback_use_case

logger = logging.getLogger("user_verification_callback")

router = APIRouter(prefix="/users/verify")


@router.get("/ping", response_class=PlainTextResponse)
def health_check():
    """Healthcheck endpoint."""
    return "pong"


@router.patch("/callback", status_code=200)
def process_verification_callback(
    payload: VerificationCallback,
    use_case: ProcessVerificationCallbackUseCase = Depends(
        get_process_verification_callback_use_case
    ),
):
    """Receive the TrueNative identity verification result.

    Verifies the ``verifyToken`` signature, maps the score to the user
    status (``VERIFICADO`` when the score is greater than 60,
    ``NO_VERIFICADO`` when it is 60 or lower), and updates the user
    through the Users service. The update is a normal synchronous request
    response call; nothing is deferred to a background task. After the
    applied update the result email is published synchronously to the
    RF-007 SNS topic (both outcomes are notified). The answer is always
    HTTP 200 on a well formed receipt: a signature mismatch or an unknown
    user discards the message without applying any change.
    """
    logger.info(
        "Verification callback received for RUV %s (user %s, score %s)",
        payload.RUV,
        payload.userIdentifier,
        payload.score,
    )
    use_case.execute(payload)
    return Response(status_code=200)
