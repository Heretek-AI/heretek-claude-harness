"""
Encryption and sanitization utilities for ExternalCallLog.

Handles encryption/decryption of request/response headers and bodies
using Fernet symmetric encryption, with sanitization for sensitive data.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import structlog

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore[misc,assignment]

CRYPTOGRAPHY_AVAILABLE = Fernet is not None

logger = structlog.get_logger("models.external_call_log_encryption")

# Maximum body size before truncation
MAX_BODY_SIZE = 10 * 1024  # 10KB
TRUNCATED_INDICATOR = "...truncated"

# Pattern for sensitive field names
SENSITIVE_PATTERN = re.compile(r"(token|key|secret|password|auth)", re.IGNORECASE)


class ExternalCallLogEncryptor:
    """
    Handles encryption and decryption of external call log data.

    Uses Fernet symmetric encryption for headers and body dictionaries.
    Provides sanitization to redact sensitive information before logging.
    """

    def __init__(self, encryption_key: str | None = None) -> None:
        """
        Initialize the encryptor.

        Args:
            encryption_key: The encryption key. If not provided, encryption
                is disabled (data stored as-is).
        """
        self._fernet: Fernet | None = None
        self._encryption_key = encryption_key
        if self._encryption_key:
            self._initialize_encryption()
        else:
            logger.warning(
                "EXTERNAL_CALL_LOG_ENCRYPTION_KEY not set - "
                "request/response data will not be encrypted"
            )

    def _initialize_encryption(self) -> None:
        """Initialize Fernet encryption."""
        if not CRYPTOGRAPHY_AVAILABLE:
            logger.error("cryptography package not installed - encryption disabled")
            return

        key_bytes: bytes
        encryption_key = self._encryption_key
        if not encryption_key:
            return

        try:
            if len(encryption_key) == 44 and encryption_key.endswith("="):
                key_bytes = encryption_key.encode()
            else:
                key_bytes = base64.urlsafe_b64encode(encryption_key.encode().ljust(32))

            if Fernet is not None:
                self._fernet = Fernet(key_bytes)
                logger.info("ExternalCallLog encryption initialized")
        except Exception as e:
            logger.error("Failed to initialize ExternalCallLog encryption", error=str(e))
            self._fernet = None

    @property
    def is_available(self) -> bool:
        """Check if encryption is available."""
        return self._fernet is not None

    def _serialize_dict(self, data: dict[str, Any]) -> str:
        """
        Serialize a dict to JSON string with truncation.

        Args:
            data: Dictionary to serialize

        Returns:
            JSON string, potentially truncated if over MAX_BODY_SIZE
        """
        json_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
        if len(json_str) > MAX_BODY_SIZE:
            json_str = json_str[:MAX_BODY_SIZE] + TRUNCATED_INDICATOR
        return json_str

    def _deserialize_dict(self, data: str) -> dict[str, Any]:
        """
        Deserialize a JSON string to dict, handling truncation.

        Args:
            data: JSON string to deserialize

        Returns:
            Dictionary, or original string if deserialization fails
        """
        if data.endswith(TRUNCATED_INDICATOR):
            logger.warning("Call log body was truncated during storage")
        try:
            result: dict[str, Any] = json.loads(data)
            return result
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to deserialize encrypted data")
            return {"_raw": data}

    def encrypt(self, data: dict[str, Any]) -> dict[str, str]:
        """
        Encrypt a dictionary (headers or body) using Fernet.

        Serializes the dict to JSON, then encrypts the string.
        Returns a dict with a single 'encrypted' key containing the ciphertext.

        Args:
            data: The dictionary to encrypt

        Returns:
            Dict with 'encrypted' key containing the encrypted ciphertext
        """
        if not data:
            return {"encrypted": ""}

        serialized = self._serialize_dict(data)

        if not self._fernet:
            return {"encrypted": serialized}

        try:
            encrypted = self._fernet.encrypt(serialized.encode())
            return {"encrypted": encrypted.decode()}
        except Exception as e:
            logger.error("Failed to encrypt external call log data", error=str(e))
            # Fall back to unencrypted storage
            return {"encrypted": serialized}

    def decrypt(self, encrypted_data: dict[str, str]) -> dict[str, Any]:
        """
        Decrypt an encrypted dictionary.

        Expects a dict with an 'encrypted' key containing the ciphertext.

        Args:
            encrypted_data: Dict with 'encrypted' key

        Returns:
            The decrypted dictionary
        """
        if not encrypted_data or "encrypted" not in encrypted_data:
            return {}

        ciphertext = encrypted_data.get("encrypted", "")

        if not ciphertext:
            return {}

        if not self._fernet:
            return self._deserialize_dict(ciphertext)

        try:
            decrypted = self._fernet.decrypt(ciphertext.encode())
            return self._deserialize_dict(decrypted.decode())
        except Exception as e:
            logger.error("Failed to decrypt external call log data", error=str(e))
            # Try to deserialize as plain text (backwards compatibility)
            return self._deserialize_dict(ciphertext)

    def sanitize(self, data: dict[str, Any], include_url: bool = True) -> dict[str, Any]:
        """
        Sanitize a dictionary by redacting sensitive information.

        Redacts:
        - Authorization headers (value replaced with '[REDACTED]')
        - API key query parameters (?key=, ?api_key=, etc.)
        - Any field matching /(token|key|secret|password|auth)/i

        Args:
            data: Dictionary to sanitize
            include_url: If True, sanitize URL query parameters

        Returns:
            Sanitized dictionary with sensitive values redacted
        """
        if not data:
            return {}

        sanitized: dict[str, Any] = {}

        for key, value in data.items():
            # Check if this is a sensitive key
            is_sensitive = SENSITIVE_PATTERN.search(key) is not None

            # Authorization header or any sensitive key
            if key.lower() == "authorization" or (is_sensitive and isinstance(value, str)):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                # Recursively sanitize nested dicts
                sanitized[key] = self.sanitize(value, include_url=False)
            elif isinstance(value, str) and include_url and "?" in value:
                # Sanitize URL query parameters
                sanitized[key] = self._sanitize_url_params(value)
            else:
                sanitized[key] = value

        return sanitized

    def _sanitize_url_params(self, url: str) -> str:
        """
        Sanitize sensitive query parameters from a URL.

        Args:
            url: URL potentially with query parameters

        Returns:
            URL with sensitive query parameters redacted
        """
        if "?" not in url:
            return url

        try:
            base_url, query = url.split("?", 1)
            params = query.split("&")
            sanitized_params: list[str] = []

            for param in params:
                if "=" in param:
                    param_name = param.split("=")[0]
                    if SENSITIVE_PATTERN.search(param_name):
                        sanitized_params.append(f"{param_name}=[REDACTED]")
                    else:
                        sanitized_params.append(param)
                else:
                    sanitized_params.append(param)

            return f"{base_url}?{'&'.join(sanitized_params)}"
        except Exception:
            # If anything goes wrong, redact the whole URL
            return "[REDACTED_URL]"


# Global encryptor instance
_encryptor: ExternalCallLogEncryptor | None = None


def get_encryptor() -> ExternalCallLogEncryptor:
    """Get or create the global encryptor instance."""
    global _encryptor
    if _encryptor is None:
        import os

        encryption_key = os.environ.get("EXTERNAL_CALL_LOG_ENCRYPTION_KEY")
        _encryptor = ExternalCallLogEncryptor(encryption_key)
    return _encryptor
