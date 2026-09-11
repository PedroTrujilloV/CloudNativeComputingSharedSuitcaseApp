"""Test suite for UsersServiceClient."""

import httpx
import pytest
from unittest.mock import Mock

from adapters.http.users_service_client import UsersServiceClient
from domain.ports.user_validation_port import AuthenticatedUser
from errors import (
    InvalidTokenError,
    TokenMissingError,
    UsersServiceUnavailableError,
)


def test_validate_token_with_200_response():
    """Calling validate_token with successful Users service response."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "user123", "username": "alice"}
    mock_client.get.return_value = mock_response

    service = UsersServiceClient(client=mock_client)
    result = service.validate_token("token_abc")

    assert result == AuthenticatedUser(id="user123", username="alice")
    mock_client.get.assert_called_once()


def test_validate_token_with_401_response():
    """Calling validate_token when Users service returns 401."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 401
    mock_client.get.return_value = mock_response

    service = UsersServiceClient(client=mock_client)
    with pytest.raises(InvalidTokenError):
        service.validate_token("invalid_token")


def test_validate_token_with_500_response():
    """Calling validate_token when Users service returns 5xx."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 500
    mock_client.get.return_value = mock_response

    service = UsersServiceClient(client=mock_client)
    with pytest.raises(UsersServiceUnavailableError):
        service.validate_token("token_abc")


def test_validate_token_with_network_error():
    """Calling validate_token when Users service is unreachable."""
    mock_client = Mock()
    mock_client.get.side_effect = httpx.HTTPError("Connection refused")

    service = UsersServiceClient(client=mock_client)
    with pytest.raises(UsersServiceUnavailableError):
        service.validate_token("token_abc")


def test_validate_token_with_empty_token():
    """Calling validate_token with empty token."""
    mock_client = Mock()
    service = UsersServiceClient(client=mock_client)
    with pytest.raises(TokenMissingError):
        service.validate_token("")
