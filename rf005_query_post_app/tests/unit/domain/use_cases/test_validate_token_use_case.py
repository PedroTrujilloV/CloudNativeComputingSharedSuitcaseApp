"""Test suite for ValidateTokenUseCase."""

import pytest

from domain.ports.user_validation_port import AuthenticatedUser
from domain.use_cases import ValidateTokenUseCase
from errors import (
    InvalidTokenError,
    TokenMissingError,
    UsersServiceUnavailableError,
)
from tests.conftest import FakeUserValidation


def test_validate_token_with_valid_token():
    """Executing with a valid token returns the authenticated user."""
    user = AuthenticatedUser(id="user1", username="alice")
    fake = FakeUserValidation(
        token_to_user={"token_abc": user},
        missing_tokens=set(),
        invalid_tokens=set(),
    )
    use_case = ValidateTokenUseCase(user_validation=fake)
    result = use_case.execute(token="token_abc")
    assert result == user


def test_validate_token_with_none_raises_token_missing_error():
    """Executing with token=None raises TokenMissingError."""
    fake = FakeUserValidation(
        token_to_user={},
        missing_tokens=set(),
        invalid_tokens=set(),
    )
    use_case = ValidateTokenUseCase(user_validation=fake)
    with pytest.raises(TokenMissingError):
        use_case.execute(token=None)


def test_validate_token_with_empty_string_raises_token_missing_error():
    """Executing with token="" raises TokenMissingError."""
    fake = FakeUserValidation(
        token_to_user={},
        missing_tokens=set(),
        invalid_tokens=set(),
    )
    use_case = ValidateTokenUseCase(user_validation=fake)
    with pytest.raises(TokenMissingError):
        use_case.execute(token="")


def test_validate_token_with_whitespace_raises_token_missing_error():
    """Executing with token="   " raises TokenMissingError."""
    fake = FakeUserValidation(
        token_to_user={},
        missing_tokens=set(),
        invalid_tokens=set(),
    )
    use_case = ValidateTokenUseCase(user_validation=fake)
    with pytest.raises(TokenMissingError):
        use_case.execute(token="   ")


def test_validate_token_with_invalid_token():
    """Executing with an invalid token propagates InvalidTokenError."""
    fake = FakeUserValidation(
        token_to_user={},
        missing_tokens=set(),
        invalid_tokens={"bad_token"},
    )
    use_case = ValidateTokenUseCase(user_validation=fake)
    with pytest.raises(InvalidTokenError):
        use_case.execute(token="bad_token")


def test_validate_token_when_service_unavailable():
    """Executing when Users service is down propagates UsersServiceUnavailableError."""
    fake = FakeUserValidation(
        token_to_user={},
        missing_tokens=set(),
        invalid_tokens=set(),
        unreachable=True,
    )
    use_case = ValidateTokenUseCase(user_validation=fake)
    with pytest.raises(UsersServiceUnavailableError):
        use_case.execute(token="token_abc")
