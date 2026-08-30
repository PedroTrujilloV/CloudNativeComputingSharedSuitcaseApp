import pytest
from errors import RouteNotFoundError, RouteAlreadyExistsError


class TestRouteNotFoundError:
    """Tests for RouteNotFoundError exception."""

    def test_route_not_found_error_is_exception(self):
        """RouteNotFoundError should be an Exception."""
        with pytest.raises(RouteNotFoundError):
            raise RouteNotFoundError()

    def test_route_not_found_error_custom_message(self):
        """RouteNotFoundError should accept custom message."""
        msg = "Custom message"
        try:
            raise RouteNotFoundError(msg)
        except RouteNotFoundError as e:
            assert str(e) == msg


class TestRouteAlreadyExistsError:
    """Tests for RouteAlreadyExistsError exception."""

    def test_route_already_exists_error_is_exception(self):
        """RouteAlreadyExistsError should be an Exception."""
        with pytest.raises(RouteAlreadyExistsError):
            raise RouteAlreadyExistsError()

    def test_route_already_exists_error_default_message(self):
        """RouteAlreadyExistsError should have default message."""
        try:
            raise RouteAlreadyExistsError()
        except RouteAlreadyExistsError as e:
            assert e.message == "Route already exists"

    def test_route_already_exists_error_custom_message(self):
        """RouteAlreadyExistsError should accept custom message."""
        msg = "Custom error message"
        try:
            raise RouteAlreadyExistsError(msg)
        except RouteAlreadyExistsError as e:
            assert e.message == msg