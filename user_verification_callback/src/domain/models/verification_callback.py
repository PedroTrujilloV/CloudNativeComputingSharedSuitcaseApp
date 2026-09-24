from pydantic import BaseModel


class VerificationCallback(BaseModel):
    """Payload delivered by TrueNative through the public webhook.

    TrueNative signs the message with ``verifyToken =
    sha256(f"{SECRET_TOKEN}:{RUV}:{SCORE}")``; the payload itself is not
    trusted until that check passes, so the ``status`` field carried by the
    provider is recorded but never applied.

    ``score`` keeps the exact JSON type (integer or floating point) because
    the signature material is the textual form of that value; coercing it
    would change the string and break a legitimate signature.
    """

    RUV: str
    userIdentifier: str
    transactionIdentifier: str | None = None
    createdAt: str | None = None
    status: str | None = None
    score: int | float
    verifyToken: str
