import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.database.models import Base
from adapters.database.user_repository_adapter import SQLAlchemyUserRepositoryAdapter
from adapters.security.password_hasher import hash_password
from domain.models.user import User, UserStatus
from errors import UserAlreadyExistsError, UserNotFoundError


@pytest.fixture
def repository():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    repo = SQLAlchemyUserRepositoryAdapter(session)
    yield repo
    session.close()


def _build_user(username: str = "ana", email: str = "ana@example.com") -> User:
    password_hash, salt = hash_password("Secret123!")
    return User(
        username=username,
        email=email,
        phoneNumber="3001234567",
        fullName="Ana Perez",
        password=password_hash,
        salt=salt,
        status=UserStatus.POR_VERIFICAR,
    )


def test_get_by_token_returns_user(repository):
    created = repository.create(_build_user())
    created.token = "opaque-token-123"
    repository.update(created)

    found = repository.get_by_token("opaque-token-123")

    assert found is not None
    assert found.id == created.id


def test_create_persists_hashed_password(repository):
    plain = "Secret123!"
    user = _build_user()

    created = repository.create(user)

    assert created.id
    assert created.password != plain
    assert created.salt
    assert created.status == UserStatus.POR_VERIFICAR
    assert repository.count() == 1
    assert repository.get_by_id(created.id) is not None
    assert repository.get_by_username("ana") is not None


def test_create_duplicate_username_raises_distinguishable_error(repository):
    repository.create(_build_user(username="ana", email="ana@example.com"))

    with pytest.raises(UserAlreadyExistsError):
        repository.create(_build_user(username="ana", email="other@example.com"))


def test_create_duplicate_email_raises_distinguishable_error(repository):
    repository.create(_build_user(username="ana", email="ana@example.com"))

    with pytest.raises(UserAlreadyExistsError):
        repository.create(_build_user(username="bob", email="ana@example.com"))


def test_update_and_delete_all(repository):
    created = repository.create(_build_user())
    created.fullName = "Ana Updated"
    created.status = UserStatus.VERIFICADO

    updated = repository.update(created)
    assert updated.fullName == "Ana Updated"
    assert updated.status == UserStatus.VERIFICADO

    repository.delete_all()
    assert repository.count() == 0


def test_update_missing_user_raises(repository):
    user = _build_user()
    user.id = "00000000-0000-0000-0000-000000000099"

    with pytest.raises(UserNotFoundError):
        repository.update(user)
