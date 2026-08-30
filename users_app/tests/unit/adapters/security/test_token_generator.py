from adapters.security.token_generator import build_expire_at, generate_opaque_token


def test_generate_opaque_token_is_not_jwt_shaped():
    token = generate_opaque_token()

    assert isinstance(token, str)
    assert len(token) >= 16
    assert token.count(".") < 2


def test_build_expire_at_is_in_the_future():
    expire_at = build_expire_at(ttl_minutes=30)

    assert expire_at is not None
