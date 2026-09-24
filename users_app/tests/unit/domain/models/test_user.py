import pytest
from pydantic import ValidationError

from domain.models.user import User, UserStatus


def test_user_defaults_to_por_verificar():
    user = User(
        username="ana",
        email="ana@example.com",
        password="hashed",
        salt="salt",
    )

    assert user.status == UserStatus.POR_VERIFICAR
    assert user.phoneNumber is None
    assert user.token is None


def test_user_defaults_to_no_ruv():
    user = User(
        username="ana",
        email="ana@example.com",
        password="hashed",
        salt="salt",
    )

    assert user.ruv is None


def test_user_stores_ruv():
    user = User(
        username="ana",
        email="ana@example.com",
        password="hashed",
        salt="salt",
        ruv="RUV-abc-123",
    )

    assert user.ruv == "RUV-abc-123"


@pytest.mark.parametrize(
    "status_value",
    ["POR_VERIFICAR", "NO_VERIFICADO", "VERIFICADO"],
)
def test_user_accepts_every_allowed_status(status_value):
    user = User(
        username="ana",
        email="ana@example.com",
        password="hashed",
        salt="salt",
        status=status_value,
    )

    assert user.status == UserStatus(status_value)


def test_user_rejects_status_outside_lifecycle():
    with pytest.raises(ValidationError):
        User(
            username="ana",
            email="ana@example.com",
            password="hashed",
            salt="salt",
            status="VERIFIED",
        )


def test_user_rejects_empty_username():
    with pytest.raises(ValidationError):
        User(username="", email="ana@example.com", password="hashed", salt="salt")
