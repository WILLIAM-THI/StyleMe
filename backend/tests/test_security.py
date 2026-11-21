"""Tests for security.py: password hashing and login tokens."""
from datetime import datetime, timedelta, timezone

import jwt

import security


def test_hash_is_not_the_plain_password():
    assert security.hash_password("mypassword") != "mypassword"


def test_correct_password_is_accepted():
    hashed = security.hash_password("mypassword")
    assert security.verify_password("mypassword", hashed) is True


def test_wrong_password_is_rejected():
    hashed = security.hash_password("mypassword")
    assert security.verify_password("wrongpassword", hashed) is False


def test_same_password_gives_different_hashes():
    # bcrypt adds a random salt, so two hashes of one password differ but both still verify
    first, second = security.hash_password("mypassword"), security.hash_password("mypassword")
    assert first != second
    assert security.verify_password("mypassword", first) and security.verify_password("mypassword", second)


def test_token_round_trip_returns_the_user_id():
    token = security.create_token(42)
    assert security.decode_token(token) == 42


def test_garbage_or_wrong_key_token_is_rejected():
    assert security.decode_token("not-a-real-token") is None
    forged = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                        "a-different-secret-key-of-32-bytes-or-more", algorithm=security.ALGORITHM)
    assert security.decode_token(forged) is None


def test_expired_token_is_rejected():
    expired = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                         security.SECRET_KEY, algorithm=security.ALGORITHM)
    assert security.decode_token(expired) is None
