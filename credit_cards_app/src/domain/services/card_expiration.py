"""Expiration handling of the presented card.

The client contract for the expiration field is ``YY/MM`` for example
``28/01`` (January 2028), and the tolerant variant ``YYYY/MM`` is also
accepted. A card is expired when its expiration month is strictly before
the current month; a card expiring in the current month is still valid
through the end of the month, which is the usual card network convention.
"""

import re
from datetime import datetime, timezone

_EXPIRATION_PATTERN = re.compile(r"^(?P<year>\d{2}|\d{4})/(0[1-9]|1[0-2])$")


def is_valid_expiration_format(value: str) -> bool:
    """Return True when the value matches the documented expiration format."""
    return bool(_EXPIRATION_PATTERN.match(value))


def expiration_year_and_month(value: str) -> tuple[int, int]:
    """Parse ``YY/MM`` or ``YYYY/MM`` into a (year, month) pair.

    Two digit years are read from the 2000 century, which covers the
    lifetime of every card that can still be valid.

    Raises:
        ValueError: the value does not match the documented format.
    """
    match = _EXPIRATION_PATTERN.match(value)
    if match is None:
        raise ValueError(
            "expirationDate must use the YY/MM format, for example 28/01"
        )
    year_text = match.group("year")
    year = int(year_text) if len(year_text) == 4 else 2000 + int(year_text)
    month = int(value.rsplit("/", 1)[1])
    return year, month


def is_expired(year: int, month: int, now: datetime) -> bool:
    """Return True when the card is expired at the given instant."""
    current = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    return (year, month) < (current.year, current.month)
