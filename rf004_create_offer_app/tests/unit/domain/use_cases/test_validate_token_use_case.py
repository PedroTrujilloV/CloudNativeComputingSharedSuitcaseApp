"""Unit tests for the ValidateTokenUseCase (authentication gate)."""

import pytest

from domain.use_cases.validate_token_use_case import ValidateTokenUseCase
from errors import InvalidTokenError, TokenMissingError, UsersServiceUnavailableError


class RecordingValidation:
    """Fake port that records calls and raises a configurable error."""

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[str] = []

    def validate_token(self, token: str):
        self.calls.append(token)
        if self.error is not None:
            raise self.error
        from domain.ports.user_validation_port import AuthenticatedUser

        return AuthenticatedUser(id="user-1", username="tester")


@pytest.mark.parametrize("token", [None, "", "   "])
def test_missing_token_raises_before_any_downstream_call(token):
    """An absent/empty token raises TokenMissingError without calling Users."""
    port = RecordingValidation()
    use_case = ValidateTokenUseCase(user_validation=port)

    with pytest.raises(TokenMissingError):
        use_case.execute(token=token)

    assert port.calls == []


def test_valid_token_returns_authenticated_user():
    """A valid token is delegated to the port and its result returned."""
    port = RecordingValidation()
    use_case = ValidateTokenUseCase(user_validation=port)

    user = use_case.execute(token="valid-token")

    assert user.id == "user-1"
    assert port.calls == ["valid-token"]


@pytest.mark.parametrize(
    "error",
    [InvalidTokenError("bad"), UsersServiceUnavailableError("down")],
)
def test_port_errors_propagate(error):
    """InvalidTokenError / UsersServiceUnavailableError propagate unchanged."""
    port = RecordingValidation(error=error)
    use_case = ValidateTokenUseCase(user_validation=port)

    with pytest.raises(type(error)):
        use_case.execute(token="valid-token")

    assert port.calls == ["valid-token"]
