from datetime import datetime, timedelta, timezone

import pytest

from domain.models.user import User, UserStatus
from domain.use_cases.get_current_user_use_case import GetCurrentUserUseCase
from errors import InvalidTokenError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _user(status, token="valid-token", expire_at=None):
    return User(
        username="ana_user",
        email="ana_user@example.com",
        password="hash",
        salt="salt",
        status=status,
        token=token,
        expireAt=(
            expire_at if expire_at is not None else _utc_now() + timedelta(minutes=60)
        ),
    )


class FakeUserRepository:
    """In-memory user repository used to exercise the use case."""

    def __init__(self, user=None):
        self.user = user

    def get_by_token(self, token):
        if self.user is not None and self.user.token == token:
            return self.user
        return None


def test_execute_returns_user_for_valid_token_of_verified_user():
    user = _user(UserStatus.VERIFICADO)
    use_case = GetCurrentUserUseCase(FakeUserRepository(user))

    assert use_case.execute(token="valid-token") is user


def test_execute_raises_for_unknown_token():
    use_case = GetCurrentUserUseCase(FakeUserRepository(_user(UserStatus.VERIFICADO)))

    with pytest.raises(InvalidTokenError):
        use_case.execute(token="missing-token")


def test_execute_raises_for_token_without_expiration():
    use_case = GetCurrentUserUseCase(FakeUserRepository(_user(UserStatus.VERIFICADO)))
    use_case.user_repository.user.expireAt = None

    with pytest.raises(InvalidTokenError):
        use_case.execute(token="valid-token")


def test_execute_raises_for_expired_token():
    expired = _utc_now() - timedelta(minutes=1)
    use_case = GetCurrentUserUseCase(
        FakeUserRepository(_user(UserStatus.VERIFICADO, expire_at=expired))
    )

    with pytest.raises(InvalidTokenError):
        use_case.execute(token="valid-token")


def test_execute_raises_for_token_of_por_verificar_user():
    use_case = GetCurrentUserUseCase(
        FakeUserRepository(_user(UserStatus.POR_VERIFICAR))
    )

    with pytest.raises(InvalidTokenError):
        use_case.execute(token="valid-token")


def test_execute_raises_for_token_of_no_verificado_user():
    use_case = GetCurrentUserUseCase(
        FakeUserRepository(_user(UserStatus.NO_VERIFICADO))
    )

    with pytest.raises(InvalidTokenError):
        use_case.execute(token="valid-token")
