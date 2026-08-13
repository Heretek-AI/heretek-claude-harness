"""Tests for gateway/auth.py — JWT creation, verification, scope enforcement (G-04)."""

import time
from pathlib import Path

import jwt
import pytest
from heretek_swarm.gateway.auth import (
    _get_jwt_secret,
    _get_jwt_audience,
    _get_jwt_issuer,
    create_jwt_token,
    verify_jwt,
    generate_api_key,
    get_api_key_from_env,
)
class TestJWTToken:
    def test_create_and_verify_valid_token(self):
        """Happy path: create then verify a valid JWT."""
        token = create_jwt_token("tester", scope="agent:read")
        assert token is not None
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # header.payload.signature

    def test_verify_returns_username(self):
        """Verify returns the sub claim on success."""
        token = create_jwt_token("alpha", scope="agent:read")
        result = verify_jwt(token)
        assert result == "alpha"

    def test_verify_rejects_expired_token(self):
        """Expired JWT returns None."""
        token = jwt.encode(
            {"sub": "test", "iat": int(time.time()) - 7200, "exp": int(time.time()) - 3600,
             "aud": _get_jwt_audience(), "iss": _get_jwt_issuer(), "scope": "agent:read"},
            _get_jwt_secret(),
            algorithm="HS256"
        )
        result = verify_jwt(token)
        assert result is None

    def test_verify_rejects_missing_sub(self):
        """No sub claim → None."""
        secret = _get_jwt_secret()
        token = jwt.encode(
            {"iat": int(time.time()), "exp": int(time.time()) + 3600,
             "aud": _get_jwt_audience(), "iss": _get_jwt_issuer()},
            secret, algorithm="HS256"
        )
        result = verify_jwt(token)
        assert result is None

    def test_verify_rejects_invalid_signature(self):
        """Wrong secret → None."""
        token = jwt.encode(
            {"sub": "tester", "iat": int(time.time()), "exp": int(time.time()) + 3600,
             "aud": _get_jwt_audience(), "iss": _get_jwt_issuer()},
            "x" * 32, algorithm="HS256"  # 32 bytes avoids InsecureKeyLengthWarning
        )
        result = verify_jwt(token)
        assert result is None

    def test_token_has_aud_iss_claims(self):
        """create_jwt_token includes aud, iss, scope claims (G-04 requirement)."""
        token = jwt.decode(
            create_jwt_token("test"), _get_jwt_secret(), algorithms=["HS256"],
            options={"verify_aud": False, "verify_iss": False},
        )
        assert "aud" in token
        assert "iss" in token
        assert "scope" in token
        assert token["aud"] == _get_jwt_audience()
        assert token["iss"] == _get_jwt_issuer()

    def test_no_aud_rejected(self):
        """JWT without aud → verify_jwt returns None (G-04)."""
        token = jwt.encode(
            {"sub": "tester", "iat": int(time.time()), "exp": int(time.time()) + 3600,
             "iss": _get_jwt_issuer(), "scope": "agent:read"},
            _get_jwt_secret(), algorithm="HS256",
        )
        assert verify_jwt(token) is None

    def test_no_iss_rejected(self):
        """JWT without iss → verify_jwt returns None."""
        token = jwt.encode(
            {"sub": "tester", "iat": int(time.time()), "exp": int(time.time()) + 3600,
             "aud": _get_jwt_audience(), "scope": "agent:read"},
            _get_jwt_secret(), algorithm="HS256",
        )
        assert verify_jwt(token) is None

    def test_wrong_aud_rejected(self):
        """JWT with wrong aud → verify_jwt returns None."""
        token = jwt.encode(
            {"sub": "tester", "iat": int(time.time()), "exp": int(time.time()) + 3600,
             "aud": "wrong-aud", "iss": _get_jwt_issuer(), "scope": "agent:read"},
            _get_jwt_secret(), algorithm="HS256",
        )
        assert verify_jwt(token) is None

    def test_wrong_iss_rejected(self):
        """JWT with wrong iss → verify_jwt returns None."""
        token = jwt.encode(
            {"sub": "tester", "iat": int(time.time()), "exp": int(time.time()) + 3600,
             "aud": _get_jwt_audience(), "iss": "wrong-iss", "scope": "agent:read"},
            _get_jwt_secret(), algorithm="HS256",
        )
        assert verify_jwt(token) is None

    def test_invalid_token_string_rejected(self):
        """Invalid token string → verify_jwt returns None."""
        assert verify_jwt("not.a.jwt") is None
        assert verify_jwt("") is None


class TestApiKey:
    def test_generate_api_key_has_prefix(self):
        key = generate_api_key()
        assert key.startswith("htsk_")
        assert len(key) > 32

    def test_get_api_key_from_env(self):
        key = get_api_key_from_env()
        assert key is not None
        assert isinstance(key, str)
