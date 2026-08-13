"""
Encryption utilities for API key encryption in configuration service.

Uses Fernet symmetric encryption with file-based key persistence.
The encryption key lives at /config/encryption.key (a named Docker volume).
On first startup, a key is auto-generated and persisted with 0o600 permissions.
On subsequent startups, the existing key is loaded and validated.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
from cryptography.fernet import Fernet

logger = structlog.get_logger("config.encryption")

# Path to the persistent encryption key file (Docker named volume).
_KEY_PATH: str = os.environ.get(
    "HERETEK_ENCRYPTION_KEY_PATH", "/config/encryption.key"
)


def _write_key_file(path: str, key_bytes: bytes) -> None:
    """Write key bytes to file with 0o600 permissions (owner-only read/write)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, key_bytes)
    finally:
        os.close(fd)


def _read_key_file(path: str) -> bytes:
    """Read key bytes from file.  Returns content on success, raises on failure."""
    fd = os.open(path, os.O_RDONLY)
    try:
        return os.read(fd, 4096)  # Fernet keys are ~44 bytes, 4096 is generous
    finally:
        os.close(fd)


class ApiKeyEncryptor:
    """
    Handles encryption and decryption of API keys.

    Uses Fernet symmetric encryption with file-based key persistence.
    The key file is read from /config/encryption.key on startup.
    If the file does not exist, a new Fernet key is generated and persisted.
    """

    def __init__(self) -> None:
        """Initialize the encryptor from the persistent key file.

        Reads /config/encryption.key; generates and persists a new key if
        the file does not exist.  Validates the loaded key with a test
        encrypt/decrypt cycle and raises RuntimeError on failure.
        """
        self._fernet: Fernet | None = None

        # Ensure the directory for the key file exists.
        key_path = Path(_KEY_PATH)
        key_dir = key_path.parent
        if str(key_dir):
            key_dir.mkdir(parents=True, exist_ok=True)

        # Load or generate the key.
        if key_path.is_file():
            key_bytes = _read_key_file(_KEY_PATH)
            logger.info("encryption_key_loaded", path=_KEY_PATH)
        else:
            key_bytes = Fernet.generate_key()
            _write_key_file(_KEY_PATH, key_bytes)
            logger.info("encryption_key_generated", path=_KEY_PATH)

        # Validate the key with a test encrypt/decrypt cycle.
        self._initialize_with_key(key_bytes)

    def _initialize_with_key(self, key_bytes: bytes) -> None:
        """Validate the provided key bytes and set up the Fernet instance."""
        try:
            candidate = Fernet(key_bytes)
            # Test encrypt/decrypt cycle to validate the key.
            test_plaintext = b"heretek-encryption-validation"
            ciphertext = candidate.encrypt(test_plaintext)
            decrypted = candidate.decrypt(ciphertext)
            if decrypted != test_plaintext:
                raise ValueError("Encryption validation round-trip mismatch")
            self._fernet = candidate
            logger.info("encryption_key_validation_passed")
        except Exception as e:
            logger.error("encryption_key_validation_failed", error=str(e))
            raise RuntimeError(
                f"Encryption key validation failed: {e}"
            ) from e

    @property
    def is_available(self) -> bool:
        """Check if encryption is available."""
        return self._fernet is not None

    def encrypt(self, api_key: str) -> str:
        """
        Encrypt an API key using Fernet symmetric encryption.

        Args:
            api_key: The plain text API key to encrypt.

        Returns:
            Encrypted API key (base64 encoded).

        Raises:
            ValueError: If encryption is not available.
        """
        if self._fernet is None:
            raise ValueError("Encryption not available — encryptor not initialized")

        try:
            encrypted = self._fernet.encrypt(api_key.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error("Failed to encrypt API key", error=str(e))
            raise ValueError(f"Encryption failed: {e}") from e

    def decrypt(self, encrypted_key: str) -> str:
        """
        Decrypt an API key using Fernet symmetric encryption.

        Args:
            encrypted_key: The encrypted API key to decrypt.

        Returns:
            Decrypted plain text API key.

        Raises:
            ValueError: If decryption fails or encryption is not available.
        """
        if self._fernet is None:
            raise ValueError("Encryption not available — encryptor not initialized")

        try:
            decrypted = self._fernet.decrypt(encrypted_key.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error("Failed to decrypt API key", error=str(e))
            raise ValueError(f"Decryption failed: {e}") from e

    def encrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Encrypt sensitive fields in a config dict.

        Encrypts fields like 'api_key', 'auth_token', 'secret' etc.
        """
        if not config:
            return {}

        sensitive_keys = {"api_key", "auth_token", "secret", "password", "credential"}
        encrypted: dict[str, Any] = {}

        for key, value in config.items():
            if (
                any(sensitive in key.lower() for sensitive in sensitive_keys)
                and isinstance(value, str)
            ):
                encrypted[key] = self.encrypt(value)
            else:
                encrypted[key] = value

        return encrypted

    def decrypt_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Decrypt sensitive fields in a config dict.
        """
        if not config:
            return {}

        sensitive_keys = {"api_key", "auth_token", "secret", "password", "credential"}
        decrypted: dict[str, Any] = {}

        for key, value in config.items():
            if (
                any(sensitive in key.lower() for sensitive in sensitive_keys)
                and isinstance(value, str)
            ):
                try:
                    decrypted[key] = self.decrypt(value)
                except ValueError:
                    decrypted[key] = value
            else:
                decrypted[key] = value

        return decrypted
