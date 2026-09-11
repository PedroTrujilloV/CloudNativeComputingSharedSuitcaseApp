"""Test suite for PostsServiceClient."""

import httpx
import pytest
from unittest.mock import Mock

from adapters.http.posts_service_client import PostsServiceClient
from domain.models import PostInfo
from errors import (
    PostNotFoundError,
    PostsServiceUnavailableError,
)


def test_get_post_with_200_response():
    """Calling get_post with successful Posts service response."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "post1", "userId": "user1"}
    mock_client.get.return_value = mock_response

    service = PostsServiceClient(client=mock_client)
    result = service.get_post("post1")

    assert result == PostInfo(id="post1", userId="user1")
    mock_client.get.assert_called_once_with("/posts/post1")


def test_get_post_maps_route_id():
    """The post's routeId is mapped so the ownership gate can pass it on."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "post1",
        "userId": "user1",
        "routeId": "route1",
    }
    mock_client.get.return_value = mock_response

    service = PostsServiceClient(client=mock_client)
    result = service.get_post("post1")

    assert result.routeId == "route1"


def test_get_post_without_route_id():
    """A payload without routeId yields routeId=None."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "post1", "userId": "user1"}
    mock_client.get.return_value = mock_response

    service = PostsServiceClient(client=mock_client)
    result = service.get_post("post1")

    assert result.routeId is None


def test_get_post_with_404_response():
    """Calling get_post when Posts service returns 404."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 404
    mock_client.get.return_value = mock_response

    service = PostsServiceClient(client=mock_client)
    with pytest.raises(PostNotFoundError):
        service.get_post("nonexistent")


def test_get_post_with_400_response():
    """Calling get_post when Posts service returns 400 (invalid ID)."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 400
    mock_client.get.return_value = mock_response

    service = PostsServiceClient(client=mock_client)
    with pytest.raises(PostNotFoundError):
        service.get_post("invalid-id")


def test_get_post_with_500_response():
    """Calling get_post when Posts service returns 5xx."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 500
    mock_client.get.return_value = mock_response

    service = PostsServiceClient(client=mock_client)
    with pytest.raises(PostsServiceUnavailableError):
        service.get_post("post1")


def test_get_post_with_network_error():
    """Calling get_post when Posts service is unreachable."""
    mock_client = Mock()
    mock_client.get.side_effect = httpx.HTTPError("Connection refused")

    service = PostsServiceClient(client=mock_client)
    with pytest.raises(PostsServiceUnavailableError):
        service.get_post("post1")
