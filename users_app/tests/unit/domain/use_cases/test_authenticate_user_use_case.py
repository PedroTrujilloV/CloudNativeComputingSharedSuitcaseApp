import pytest

from adapters.security.password_hasher import hash_password
from domain.models.user import User, UserStatus
from domain.use_cases.authenticate_user_use_case import AuthenticateUserUseCase
from errors import UserNotFoundError, UserNotVerifiedError


class FakeUserRepository:
    """In-memory user repository used to exercise the use case."""

    def __init__(self):
        self.users = {}
        self.updated = []

    def add(self, user):
        user.id = user.id or f"id-{len(self.users) + 1}"
        self.users[user.username] = user
        return user

    def get_by_username(self, username):
        return self.users.get(username)

    def update(self, user):
        self.updated.append(user)
        return user


def _user(status, username="ana_user"):
    password_hash, salt = hash_password("Secret123!", salt="ab" * 16)
    return User(
        username=username,
        email=f"{username}@example.com",
        password=password_hash,
        salt=salt,
        status=status,
    )


def test_execute_issues_token_for_verified_user():
    repository = FakeUserRepository()
    user = _user(UserStatus.VERIFICADO)
    repository.add(user)

    use_case = AuthenticateUserUseCase(repository)
    issued = use_case.execute(username="ana_user", password="Secret123!")

    assert issued.token
    assert issued.expireAt is not None
    assert repository.updated == [user]


def test_execute_rejects_por_verificar_user_without_persisting_a_token():
    repository = FakeUserRepository()
    repository.add(_user(UserStatus.POR_VERIFICAR))

    use_case = AuthenticateUserUseCase(repository)

    with pytest.raises(UserNotVerifiedError):
        use_case.execute(username="ana_user", password="Secret123!")

    stored = repository.users["ana_user"]
    assert stored.token is None
    assert stored.expireAt is None
    assert repository.updated == []


def test_execute_rejects_no_verificado_user_without_persisting_a_token():
    repository = FakeUserRepository()
    repository.add(_user(UserStatus.NO_VERIFICADO))

    use_case = AuthenticateUserUseCase(repository)

    with pytest.raises(UserNotVerifiedError):
        use_case.execute(username="ana_user", password="Secret123!")

    stored = repository.users["ana_user"]
    assert stored.token is None
    assert stored.expireAt is None
    assert repository.updated == []


def test_execute_raises_user_not_found_for_invalid_credentials():
    repository = FakeUserRepository()
    repository.add(_user(UserStatus.VERIFICADO))

    use_case = AuthenticateUserUseCase(repository)

    with pytest.raises(UserNotFoundError):
        use_case.execute(username="ana_user", password="WrongPassword!")

    with pytest.raises(UserNotFoundError):
        use_case.execute(username="missing_user", password="Secret123!")

    assert repository.users["ana_user"].token is None
    assert repository.updated == []
