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


def test_user_rejects_empty_username():
    with pytest.raises(ValidationError):
        User(username="", email="ana@example.com", password="hashed", salt="salt")
