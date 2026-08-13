"""SOPS-encrypted secrets decryption loader at startup.

Provides the SecretsLoader class that decrypts encrypted secrets (using SOPS
and age) at application startup and injects them into os.environ.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger("config.secrets_loader")

# Canonical paths relative to the repository root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SECRETS_DIR = REPO_ROOT / "secrets"
ENCRYPTED_ENV_FILE = SECRETS_DIR / "encrypted.env"
CI_YAML_FILE = SECRETS_DIR / "ci.yaml"
DOTENV_FILE = REPO_ROOT / ".env"


class SecretsLoader:
    """Decrypts SOPS-encrypted secrets at startup and injects them into environment."""

    def __init__(
        self,
        environment: str | None = None,
        sops_age_key: str | None = None,
    ) -> None:
        self.environment = environment or os.environ.get("ENVIRONMENT", "development")
        self._sops_age_key = sops_age_key if sops_age_key is not None else os.environ.get("SOPS_AGE_KEY")
        self._sops_binary: str | None = None

    def _ensure_sops_binary(self) -> None:
        """Find the SOPS binary path, or raise RuntimeError."""
        sops = shutil.which("sops")
        if sops is None:
            # Check common fallback paths
            for candidate in (
                Path.home() / ".local" / "bin" / "sops",
                Path("/usr/local/bin/sops"),
                Path("/opt/homebrew/bin/sops"),
                Path("/usr/bin/sops"),
            ):
                if candidate.is_file():
                    sops = str(candidate)
                    break
        if sops is None:
            msg = "SOPS binary not found. Install SOPS or add to PATH."
            logger.error("sops_binary_not_found", error=msg)
            raise RuntimeError(msg)
        self._sops_binary = sops

    @staticmethod
    def _inject_env_from_text(text: str) -> int:
        """Parse key-value pairs from plaintext and inject into environment.

        Comments starting with '#' and blank lines are ignored.
        Existing environment variables are NOT overwritten.
        """
        count = 0
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Strip wrapping quotes
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                if key not in os.environ:
                    os.environ[key] = val
                    count += 1
        return count

    async def _decrypt_file(self, path: Path) -> str:
        """Decrypt a SOPS encrypted file using sops CLI and return stdout."""
        self._ensure_sops_binary()
        if not path.exists():
            raise FileNotFoundError(f"Encrypted file not found: {path}")

        env = os.environ.copy()
        if self._sops_age_key:
            env["SOPS_AGE_KEY"] = self._sops_age_key

        proc = await asyncio.create_subprocess_exec(
            self._sops_binary,
            "--decrypt",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error_msg = (
                stderr.decode(errors="replace").strip()
                or stdout.decode(errors="replace").strip()
            )
            logger.error("sops_decrypt_failed", path=str(path), error=error_msg)
            raise RuntimeError(f"sops --decrypt {path} exited {proc.returncode}: {error_msg}")
        return stdout.decode(errors="replace")

    async def load_secrets(self) -> None:
        """Decrypt secrets/encrypted.env and inject keys into environment."""
        if self.environment == "production" and not self._sops_age_key:
            raise RuntimeError(
                "SOPS_AGE_KEY is required in production mode. Set the SOPS_AGE_KEY "
                "environment variable to decrypt secrets."
            )

        if not self._sops_age_key and self.environment == "development":
            # Fallback path for development
            if DOTENV_FILE.exists():
                try:
                    text = DOTENV_FILE.read_text(encoding="utf-8")
                    count = self._inject_env_from_text(text)
                    logger.warning(
                        "secrets_fallback_dev",
                        reason="SOPS_AGE_KEY not set, loaded from .env",
                        injected_count=count,
                    )
                    return
                except Exception as e:
                    logger.warning("dev_fallback_failed", error=str(e))
            else:
                logger.warning("dev_fallback_skipped", reason=".env file not found")
                return

        # Attempt decryption
        try:
            decrypted = await self._decrypt_file(ENCRYPTED_ENV_FILE)
            count = self._inject_env_from_text(decrypted)
            logger.info("secrets_loaded_successfully", path=str(ENCRYPTED_ENV_FILE), count=count)
        except Exception as e:
            if self.environment == "development":
                logger.warning(
                    "secrets_fallback_dev",
                    reason=f"Decryption failed ({e}), falling back to .env",
                )
                if DOTENV_FILE.exists():
                    text = DOTENV_FILE.read_text(encoding="utf-8")
                    count = self._inject_env_from_text(text)
                    logger.warning(
                        "secrets_fallback_dev",
                        reason="Loaded from .env after decryption failure",
                        injected_count=count,
                    )
                else:
                    logger.warning("dev_fallback_skipped", reason=".env file not found")
            else:
                raise

    async def load_ci_secrets(self) -> None:
        """Decrypt secrets/ci.yaml and inject keys into environment."""
        try:
            decrypted = await self._decrypt_file(CI_YAML_FILE)
            data = yaml.safe_load(decrypted)
            if isinstance(data, dict):
                count = 0
                for k, v in data.items():
                    if k not in os.environ and v is not None:
                        os.environ[k] = str(v)
                        count += 1
                logger.info("ci_secrets_loaded", path=str(CI_YAML_FILE), injected_count=count)
            else:
                logger.warning("ci_secrets_invalid_yaml", path=str(CI_YAML_FILE))
        except Exception as e:
            logger.error("ci_secrets_load_failed", error=str(e))
            raise


def get_secrets_loader() -> SecretsLoader:
    """Get canonical SecretsLoader instance."""
    return SecretsLoader()
