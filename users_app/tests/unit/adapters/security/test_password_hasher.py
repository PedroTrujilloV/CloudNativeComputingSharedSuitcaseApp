from adapters.security.password_hasher import (
    generate_salt,
    hash_password,
    verify_password,
)


def test_hash_password_does_not_return_plaintext():
    plain = "Secret123!"
    password_hash, salt = hash_password(plain)

    assert password_hash != plain
    assert salt
    assert plain not in password_hash


def test_verify_password_accepts_matching_secret():
    plain = "Secret123!"
    password_hash, salt = hash_password(plain)

    assert verify_password(plain, password_hash, salt) is True
    assert verify_password("wrong", password_hash, salt) is False


def test_same_password_with_different_salts_produces_different_hashes():
    plain = "Secret123!"
    hash_one, salt_one = hash_password(plain, salt=generate_salt())
    hash_two, salt_two = hash_password(plain, salt=generate_salt())

    assert salt_one != salt_two
    assert hash_one != hash_two
