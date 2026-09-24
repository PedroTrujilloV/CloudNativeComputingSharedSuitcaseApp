from datetime import datetime, timedelta, timezone

from domain.models.user import UserStatus
from domain.use_cases.create_user_use_case import CreateUserUseCase
from errors import TrueNativeRequestError, TrueNativeUnreachableError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FakeUserRepository:
    """In-memory user repository used to exercise the use case."""

    def __init__(self):
        self.users = {}
        self.created = []
        self.updated = []
        self.ruv_updates = []

    def create(self, user):
        user.id = f"id-{len(self.users) + 1}"
        user.createdAt = _utc_now()
        user.updatedAt = user.createdAt
        self.users[user.id] = user
        self.created.append(user)
        return user

    def get_by_id(self, user_id):
        return self.users.get(user_id)

    def get_by_username(self, username):
        return next((u for u in self.users.values() if u.username == username), None)

    def get_by_token(self, token):
        return next((u for u in self.users.values() if u.token == token), None)

    def update(self, user):
        self.updated.append(user)
        user.updatedAt = _utc_now()
        return user

    def set_ruv(self, user_id, ruv):
        user = self.users[user_id]
        user.ruv = ruv
        self.ruv_updates.append((user_id, ruv))
        return user

    def count(self):
        return len(self.users)

    def delete_all(self):
        self.users.clear()


class FakeProvider:
    """Verification provider that returns a fixed RUV or raises a fixed error."""

    def __init__(self, ruv="ruv-1", error=None):
        self.ruv = ruv
        self.error = error
        self.calls = []

    def request_verification(self, *, user, user_identifier, transaction_identifier):
        self.calls.append(
            {
                "user": user,
                "user_identifier": user_identifier,
                "transaction_identifier": transaction_identifier,
            }
        )
        if self.error is not None:
            raise self.error
        return self.ruv


def _use_case(repository, provider):
    return CreateUserUseCase(repository, provider)


def _args(**overrides):
    data = {
        "username": "ana_user",
        "password": "Secret123!",
        "email": "ana@example.com",
        "dni": "123456",
        "fullName": "Ana Perez",
        "phoneNumber": "3001234567",
    }
    data.update(overrides)
    return data


def test_execute_creates_por_verificar_and_stores_ruv():
    repository = FakeUserRepository()
    provider = FakeProvider(ruv="ruv-1")

    user = _use_case(repository, provider).execute(**_args())

    assert user.id == "id-1"
    assert user.status == UserStatus.POR_VERIFICAR
    assert user.ruv == "ruv-1"
    assert len(repository.created) == 1
    assert repository.created[0].status == UserStatus.POR_VERIFICAR
    assert repository.ruv_updates == [("id-1", "ruv-1")]
    assert repository.updated == []


def test_execute_sends_available_fields_and_stored_identifier():
    repository = FakeUserRepository()
    provider = FakeProvider()

    user = _use_case(repository, provider).execute(**_args())

    call = provider.calls[0]
    assert call["user_identifier"] == user.id
    assert call["transaction_identifier"]
    sent = call["user"]
    assert sent.email == "ana@example.com"
    assert sent.dni == "123456"
    assert sent.fullName == "Ana Perez"
    assert sent.phoneNumber == "3001234567"


def test_execute_uses_unique_transaction_identifier_per_call():
    repository = FakeUserRepository()
    provider = FakeProvider()

    _use_case(repository, provider).execute(**_args())
    _use_case(repository, provider).execute(**_args(username="other_user"))

    identifiers = [call["transaction_identifier"] for call in provider.calls]
    assert identifiers[0] != identifiers[1]


def test_execute_marks_no_verificado_when_provider_rejects():
    repository = FakeUserRepository()
    provider = FakeProvider(error=TrueNativeRequestError(401, "bad token"))

    user = _use_case(repository, provider).execute(**_args())

    assert user.status == UserStatus.NO_VERIFICADO
    assert user.ruv is None
    assert repository.ruv_updates == []
    assert len(repository.updated) == 1
    assert repository.updated[0].id == user.id
    assert repository.users[user.id].status == UserStatus.NO_VERIFICADO


def test_execute_marks_no_verificado_when_provider_is_unreachable():
    repository = FakeUserRepository()
    provider = FakeProvider(error=TrueNativeUnreachableError("connection refused"))

    user = _use_case(repository, provider).execute(**_args())

    assert user.status == UserStatus.NO_VERIFICADO
    assert user.ruv is None
    assert repository.users[user.id].status == UserStatus.NO_VERIFICADO


def test_execute_refreshes_updated_at_on_failure():
    repository = FakeUserRepository()
    provider = FakeProvider(error=TrueNativeRequestError(409, "pending"))
    use_case = _use_case(repository, provider)

    user = use_case.execute(**_args())
    stale = user.updatedAt - timedelta(hours=1)
    repository.users[user.id].updatedAt = stale

    result = use_case.execute(**_args(username="other_user"))

    assert result.status == UserStatus.NO_VERIFICADO
    assert repository.users[result.id].updatedAt > stale


def test_execute_keeps_created_user_when_provider_fails():
    repository = FakeUserRepository()
    provider = FakeProvider(error=TrueNativeUnreachableError("connection refused"))

    user = _use_case(repository, provider).execute(**_args())

    assert repository.count() == 1
    stored = repository.get_by_id(user.id)
    assert stored is not None
    assert stored.username == "ana_user"
    assert stored.status == UserStatus.NO_VERIFICADO
