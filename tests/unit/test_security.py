from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_verifies_original_password():
    hashed = hash_password("password123")

    assert hashed != "password123"
    assert verify_password("password123", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_contains_subject_and_type():
    token = create_access_token("user-id")

    payload = decode_token(token)

    assert payload["sub"] == "user-id"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_refresh_token_contains_subject_and_type():
    token = create_refresh_token("user-id")

    payload = decode_token(token)

    assert payload["sub"] == "user-id"
    assert payload["type"] == "refresh"


def test_decode_token_rejects_expired_token():
    expired = jwt.encode(
        {
            "sub": "user-id",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired)
