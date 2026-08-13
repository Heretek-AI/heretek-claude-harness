"""
Authentication Layer for Heretek Swarm Gateway

Bearer token authentication for all gateway endpoints.
Security First: Auth enabled by default, no hardcoded credentials.

Supports JWT tokens (with expiry) alongside the legacy static HERETEK_API_KEY.
JWT is tried first; on failure, the static key comparison is the fallback.

Reference: Prime Directive Security First principle
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, UTC
from typing import Any

import jwt
import structlog
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = structlog.get_logger(__name__)

# Security configuration
security = HTTPBearer(auto_error=False)


def _get_jwt_secret() -> str:
    """Return the JWT secret from the environment.

    Raises:
        RuntimeError: If ENVIRONMENT=production and JWT_SECRET is empty/None.
    """
    secret = os.getenv("JWT_SECRET", "").strip()
    environment = os.getenv("ENVIRONMENT", "development")

    if not secret:
        if environment == "production":
            logger.error("jwt_secret_missing_production")
            raise RuntimeError(
                "JWT_SECRET required in production. "
                "Generate with: export JWT_SECRET=$(openssl rand -hex 32)"
            )
        secret = "dev-only-jwt-secret-do-not-use-in-production-9d4f8a2c1b7e3f5a"
        logger.warning(
            "jwt_secret_default_development",
            message=(
                "Using static dev JWT_SECRET. Set JWT_SECRET env var "
                "for persistence across processes."
            ),
        )

    return secret


def _get_jwt_audience() -> str:
    return os.getenv("JWT_AUDIENCE", "heretek-swarm")


def _get_jwt_issuer() -> str:
    return os.getenv("JWT_ISSUER", "heretek-swarm")


def create_jwt_token(
    username: str,
    expiry_hours: int = 24,
    scope: str = "agent:read",
) -> str:
    """Create a signed JWT token for the given username.

    Args:
        username: Subject claim (sub).
        expiry_hours: Token lifetime in hours (default 24).
        scope: OAuth-style scope claim (default "agent:read").

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(hours=expiry_hours),
        "aud": _get_jwt_audience(),
        "iss": _get_jwt_issuer(),
        "scope": scope,
    }
    secret = _get_jwt_secret()
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_jwt(token: str) -> str | None:
    """Decode and validate a JWT token.

    Args:
        token: Raw JWT string.

    Returns:
        Username (sub claim) on success, ``None`` on any failure.
    """
    secret = _get_jwt_secret()
    audience = _get_jwt_audience()
    issuer = _get_jwt_issuer()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        logger.warning("auth_jwt_expired")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("auth_jwt_invalid", reason=str(exc))
        return None

    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        logger.warning("auth_jwt_invalid", reason="missing_or_empty_sub")
        return None

    return username


def generate_api_key() -> str:
    """
    Generate secure API key.

    Returns:
        Secure random API key with heretek prefix
    """
    return f"htsk_{secrets.token_urlsafe(32)}"


def get_api_key_from_env() -> str:
    """
    Get API key from environment, generate if missing.

    Returns:
        API key string

    Raises:
        RuntimeError: If in production without API key
    """
    key = os.getenv("HERETEK_API_KEY")

    if not key:
        # Check if production
        environment = os.getenv("ENVIRONMENT", "development")

        if environment == "production":
            logger.error("api_key_missing_production")
            raise RuntimeError(
                "HERETEK_API_KEY required in production. "
                "Generate with: export HERETEK_API_KEY=$(openssl rand -hex 32)"
            )

        key = generate_api_key()
        logger.warning(
            "api_key_generated_development",
            message="Set HERETEK_API_KEY environment variable",
        )

    return key


async def verify_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str:
    """
    Verify Bearer token authentication.

    Tries JWT first, then falls back to static API key comparison.

    Args:
        credentials: HTTP Authorization credentials

    Returns:
        "authenticated" if valid

    Raises:
        HTTPException: If auth fails
    """
    if credentials is None:
        logger.warning("auth_missing_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 1. Try JWT first
    username = verify_jwt(token)
    if username is not None:
        logger.info("auth_jwt_success", username=username)
        return "authenticated"

    # 2. Fall back to static API key comparison
    expected_key = get_api_key_from_env()
    if token == expected_key:
        logger.debug("auth_success")
        return "authenticated"

    # Neither worked
    logger.warning("auth_invalid_token")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def optional_auth(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str | None:
    """
    Optional authentication — returns None if no credentials.

    Use for endpoints that work with or without auth.

    Args:
        credentials: HTTP Authorization credentials

    Returns:
        "authenticated" if valid, None otherwise
    """
    if credentials is None:
        return None

    token = credentials.credentials

    # Try JWT first
    username = verify_jwt(token)
    if username is not None:
        return "authenticated"

    # Fall back to static key
    expected_key = get_api_key_from_env()
    if token == expected_key:
        return "authenticated"

    return None


def get_api_key_header() -> dict:
    """Get API key for outbound requests."""
    key = get_api_key_from_env()
    return {"Authorization": f"Bearer {key}"}


# =============================================================================
# Shared TokenStore (Phase 2.10 of PLAN.md — consolidate auth)
# =============================================================================


class TokenStore:
    """In-memory short-lived token store shared by every subsystem.

    Replaces the three duplicated ``*AuthManager`` classes that
    previously lived in ``api/consensus.py`` (``ConsensusAuthManager``)
    and ``api/websockets.py`` (``WebSocketAuthManager``). Each one
    reimplemented token-issue / validate / revoke / permission-check
    with subtle semantic drift; per the audit (§1.7), three trust
    decisions for the same request is a direct Prime Directive
    zero-trust violation.

    This ``TokenStore`` is the canonical implementation. The two
    legacy classes now subclass it and add their subsystem-specific
    extras (rate limiting on the WebSocket side, permissions on the
    consensus side) on top. New code should use ``TokenStore``
    directly.

    Notes
    -----
    * In-memory only. A cluster deployment should replace this with
      Redis (the slowapi pattern at ``security/rate_limiter.py``
      already uses ``REDIS_URL`` for that).
    * 24-hour default expiry matches the legacy behavior.
    """

    def __init__(self, expiry_hours: int = 24) -> None:
        self._tokens: dict[str, dict[str, Any]] = {}
        self._permissions: dict[str, list[str]] = {}
        self._expiry = timedelta(hours=expiry_hours)

    def generate_token(
        self,
        subject: str,
        permissions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Issue a new opaque token bound to ``subject`` (agent id,
        user id, etc). Returns the raw token string.
        """
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        self._tokens[token] = {
            "subject": subject,
            "created_at": now,
            "expires_at": now + self._expiry,
            "metadata": metadata or {},
        }
        if permissions:
            self._permissions[subject] = permissions
        return token

    def validate_token(self, token: str) -> tuple[bool, str | None, str | None]:
        """Return ``(is_valid, subject, error_message)``.

        Expired tokens are deleted on access so the dict cannot grow
        unbounded.
        """
        if not token:
            return False, None, "Token required"
        record = self._tokens.get(token)
        if record is None:
            return False, None, "Invalid token"
        if datetime.now(UTC) > record["expires_at"]:
            del self._tokens[token]
            return False, None, "Token expired"
        return True, record["subject"], None

    def check_permission(self, subject: str, operation: str) -> bool:
        """Return True if ``subject`` has been granted ``operation``."""
        return operation in self._permissions.get(subject, [])

    def revoke_token(self, token: str) -> bool:
        """Revoke ``token``; returns True if it was valid and removed."""
        record = self._tokens.pop(token, None)
        if record is None:
            return False
        subject = record["subject"]
        # Only drop permissions if no other live token references them.
        if not any(
            r["subject"] == subject
            for t, r in self._tokens.items()
            if t != token
        ):
            self._permissions.pop(subject, None)
        return True

    def __len__(self) -> int:
        return len(self._tokens)


# Process-wide default store. Subsystems that need a private store
# (e.g. for unit tests) can construct their own ``TokenStore()``.
default_token_store: TokenStore = TokenStore()
