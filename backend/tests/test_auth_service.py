from datetime import timedelta
import pytest
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


def test_password_hashing_and_verification():
    raw_password = "SecurePassword123!"
    hashed = hash_password(raw_password)

    # Hash should be a non-empty string and not equal to raw password
    assert isinstance(hashed, str)
    assert hashed != raw_password
    assert hashed.startswith("$2b$")

    # Verification must succeed with correct password
    assert verify_password(raw_password, hashed) is True

    # Verification must fail with wrong password
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


def test_password_salt_uniqueness():
    password = "SamePasswordForEachHash"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    # Even for the exact same password, bcrypt must produce unique salts
    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_token_creation_and_decoding():
    payload = {"sub": "42", "email": "test@example.com"}
    token = create_access_token(payload)

    assert isinstance(token, str)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "42"
    assert decoded["email"] == "test@example.com"
    assert "exp" in decoded


def test_expired_token_rejected():
    payload = {"sub": "42", "email": "test@example.com"}
    # Create token already expired in the past
    expired_token = create_access_token(payload, expires_delta=timedelta(seconds=-10))

    decoded = decode_access_token(expired_token)
    assert decoded is None


def test_tampered_token_rejected():
    payload = {"sub": "42", "email": "test@example.com"}
    valid_token = create_access_token(payload)
    # Tamper with the token characters
    tampered_token = valid_token[:-4] + "abcd"

    decoded = decode_access_token(tampered_token)
    assert decoded is None
