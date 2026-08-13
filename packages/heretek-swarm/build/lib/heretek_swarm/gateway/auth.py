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
from datetime import datetime, timedelta, timezone

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
    now = datetime.now(timezone.utc)
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
    credentials: HTTPAuthorizationCredentials | None = Security(security),  # noqa: B008
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
    credentials: HTTPAuthorizationCredentials | None = Security(security),  # noqa: B008
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
