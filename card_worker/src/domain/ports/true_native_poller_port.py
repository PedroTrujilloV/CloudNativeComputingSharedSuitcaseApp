from abc import ABC, abstractmethod
from dataclasses import dataclass

# Terminal statuses documented by the TrueNative polling model: the
# platform answers GET /native/cards/{ruv} with 202 while the
# verification is in progress and with 200 carrying one of these values
# when it finishes.
TERMINAL_STATUSES = ("APROBADA", "RECHAZADA")


@dataclass(frozen=True)
class CardPollingResult:
    """Outcome of one polling attempt against TrueNative."""

    terminal: bool
    status: str | None = None  # terminal status when terminal is True


class TrueNativeCardPollerPort(ABC):
    """Port that checks the card verification state at TrueNative."""

    @abstractmethod
    def check_status(self, ruv: str) -> CardPollingResult:
        """Check ``GET /native/cards/{ruv}`` once.

        A non terminal answer (the platform still processing) is returned
        with ``terminal=False``; a terminal answer carries the final
        status (one of ``TERMINAL_STATUSES``).
        """
