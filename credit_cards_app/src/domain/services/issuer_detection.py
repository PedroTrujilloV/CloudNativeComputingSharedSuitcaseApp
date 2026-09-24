"""Issuer detection from the card BIN (bank identification number).

The issuer is derived at creation time from the leading digits of the card
number, with ``UNKNOWN`` as the fallback. This mirrors what the TrueNative
platform derives from the BIN, so the application can also fall back to its
own detection when the platform response does not carry a usable issuer.
"""

from domain.models.credit_card import CardIssuer

# Leading digit or prefix ranges per issuer. The ranges follow the public
# BIN assignments of each network; anything outside them is UNKNOWN.
_VISA_FIRST_DIGIT = "4"
_MASTERCARD_FIRST_TWO = {"51", "52", "53", "54", "55"}
_MASTERCARD_FIRST_FOUR = range(2221, 2721)
_AMERICAN_EXPRESS_FIRST_TWO = {"34", "37"}
_DISCOVER_FIRST_FOUR = {6011}
_DISCOVER_FIRST_TWO = {"62", "65"}
_DISCOVER_SIX_RANGE = range(622126, 626300)
_DINERS_FIRST_THREE = range(300, 306)
_DINERS_FIRST_TWO = {"36", "38", "39"}


def detect_issuer_from_bin(card_number: str) -> CardIssuer:
    """Derive the issuer from the card number, with UNKNOWN as fallback.

    The input is assumed to be a valid card number (digits only); the
    detection is best effort by design, so an unrecognized prefix always
    yields ``CardIssuer.UNKNOWN`` instead of an error.
    """
    digits = card_number
    first2 = digits[:2]
    first3 = digits[:3]
    first4 = digits[:4]

    try:
        int4 = int(first4)
        int6 = int(digits[:6]) if len(digits) >= 6 else None
    except ValueError:
        return CardIssuer.UNKNOWN

    if first2 in _AMERICAN_EXPRESS_FIRST_TWO:
        return CardIssuer.AMERICAN_EXPRESS
    if digits.startswith(_VISA_FIRST_DIGIT):
        return CardIssuer.VISA
    if first2 in _MASTERCARD_FIRST_TWO:
        return CardIssuer.MASTERCARD
    if int4 in _MASTERCARD_FIRST_FOUR:
        return CardIssuer.MASTERCARD
    if int4 in _DISCOVER_FIRST_FOUR or (
        first2 in _DISCOVER_FIRST_TWO and int6 in _DISCOVER_SIX_RANGE
    ) or first2 == "65":
        return CardIssuer.DISCOVER
    if int(first3) in _DINERS_FIRST_THREE or first2 in _DINERS_FIRST_TWO:
        return CardIssuer.DINERS_CLUB
    return CardIssuer.UNKNOWN
