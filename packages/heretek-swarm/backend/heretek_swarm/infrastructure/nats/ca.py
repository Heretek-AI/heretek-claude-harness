"""
Certificate Authority for NATS TLS.

Provides a CertificateAuthority class that generates a root CA and issues
short-lived (90-day) agent certificates.  Certificates are serialised to PEM
and stored in SOPS-encrypted YAML (``secrets/certs.yaml``), consistent with
the existing ``.sops.yaml`` age-based encryption rules.

Convenience functions mirror the ``SecretsLoader`` subprocess pattern for SOPS
encrypt/decrypt operations.

Structured log events:
    certificate_generated        — cert_type, subject, expiry (ISO 8601)
    certificate_renewal_needed   — days_remaining, subject
    certificate_renewal_completed — new_expiry (ISO 8601)
    certs_encrypted              — path, result
    certs_decrypted              — path
    certs_encrypt_failed         — path, error
    certs_decrypt_failed         — path, error
"""

from __future__ import annotations

import asyncio
import datetime
import ipaddress
import os
import shutil
import tempfile
from pathlib import Path

import structlog
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

logger = structlog.get_logger("infrastructure.nats.ca")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
SECRETS_DIR = REPO_ROOT / "secrets"
CERTS_YAML_PATH = SECRETS_DIR / "certs.yaml"

CA_CN = "Heretek Swarm Root CA"
CA_KEY_SIZE = 4096
CA_VALIDITY_DAYS = 365
AGENT_KEY_SIZE = 2048
AGENT_VALIDITY_DAYS = 90
RENEWAL_THRESHOLD_DAYS = 30  # Log renewal-needed when ≤ 30 days remain


# ---------------------------------------------------------------------------
# CertificateAuthority
# ---------------------------------------------------------------------------


class CertificateAuthority:
    """Generates a self-signed CA root and issues agent certificates.

    The CA root key and certificate are generated in the constructor.
    Agent certificates are issued via ``issue_agent_cert()`` and are valid
    for 90 days.

    Parameters:
        common_name: Subject CN for the root CA certificate.
        key_size: RSA key size for the root CA (default 4096).
        validity_days: Validity period for the root CA (default 365).
        agent_key_size: RSA key size for agent certificates (default 2048).
        agent_validity_days: Validity period for agent certs (default 90).
    """

    def __init__(
        self,
        common_name: str = CA_CN,
        key_size: int = CA_KEY_SIZE,
        validity_days: int = CA_VALIDITY_DAYS,
        agent_key_size: int = AGENT_KEY_SIZE,
        agent_validity_days: int = AGENT_VALIDITY_DAYS,
    ) -> None:
        self._common_name = common_name
        self._key_size = key_size
        self._validity_days = validity_days
        self._agent_key_size = agent_key_size
        self._agent_validity_days = agent_validity_days

        # Generate CA root key
        self._ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self._key_size,
        )

        # Build self-signed CA cert
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, self._common_name),
        ])
        self._ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(self._ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.UTC))
            .not_valid_after(
                datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(days=self._validity_days)
            )
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    key_cert_sign=True,
                    crl_sign=True,
                    digital_signature=False,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(
                    self._ca_key.public_key()
                ),
                critical=False,
            )
            .sign(self._ca_key, hashes.SHA256())
        )

        logger.info(
            "certificate_generated",
            cert_type="ca_root",
            subject=self._common_name,
            expiry=self._ca_cert.not_valid_after_utc.isoformat(),
        )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def ca_cert_pem(self) -> str:
        """The CA root certificate as a PEM-encoded string."""
        return self._ca_cert.public_bytes(serialization.Encoding.PEM).decode(
            "ascii"
        )

    @property
    def ca_key_pem(self) -> str:
        """The CA root private key as a PEM-encoded string."""
        return self._ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")

    @property
    def expiry(self) -> datetime.datetime:
        """The CA cert expiry as a timezone-aware UTC datetime."""
        return self._ca_cert.not_valid_after_utc

    # ------------------------------------------------------------------
    # Agent certificate issuance
    # ------------------------------------------------------------------

    def issue_agent_cert(
        self, agent_id: str
    ) -> dict[str, str]:
        """Issue a short-lived certificate for an agent.

        Parameters:
            agent_id: The agent identifier — used as the certificate CN.

        Returns:
            A dict with keys ``"cert"`` and ``"key"``, each containing the
            PEM-encoded certificate and private key respectively.
        """
        # Generate agent key
        agent_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self._agent_key_size,
        )

        # Build CSR
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                x509.Name([
                    x509.NameAttribute(NameOID.COMMON_NAME, agent_id),
                ])
            )
            .sign(agent_key, hashes.SHA256())
        )

        # Sign with CA
        not_valid_before = datetime.datetime.now(datetime.UTC)
        not_valid_after = not_valid_before + datetime.timedelta(
            days=self._agent_validity_days
        )

        agent_cert = (
            x509.CertificateBuilder()
            .subject_name(csr.subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(csr.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(not_valid_before)
            .not_valid_after(not_valid_after)
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                ]),
                critical=False,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(
                    agent_key.public_key()
                ),
                critical=False,
            )
            .sign(self._ca_key, hashes.SHA256())
        )

        # Check renewal threshold
        days_remaining = (not_valid_after - datetime.datetime.now(datetime.UTC)).days
        if days_remaining <= RENEWAL_THRESHOLD_DAYS:
            logger.warning(
                "certificate_renewal_needed",
                days_remaining=days_remaining,
                subject=agent_id,
            )
        else:
            logger.info(
                "certificate_generated",
                cert_type="agent",
                subject=agent_id,
                expiry=not_valid_after.isoformat(),
            )

        return {
            "cert": agent_cert.public_bytes(
                serialization.Encoding.PEM
            ).decode("ascii"),
            "key": agent_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("ascii"),
        }

    def issue_server_cert(
        self, hostname: str = "nats-server"
    ) -> dict[str, str]:
        """Issue a server certificate for the NATS server.

        The certificate includes SANs for ``localhost``, ``nats`` (Docker
        service name), ``127.0.0.1``, and the given *hostname*.  This allows
        the same certificate to work in both local-dev and Docker contexts.

        Parameters:
            hostname: Primary CN for the server certificate.

        Returns:
            A dict with keys ``"cert"`` and ``"key"``, each containing the
            PEM-encoded certificate and private key respectively.
        """
        server_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self._agent_key_size,
        )

        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                x509.Name([
                    x509.NameAttribute(NameOID.COMMON_NAME, hostname),
                ])
            )
            .sign(server_key, hashes.SHA256())
        )

        not_valid_before = datetime.datetime.now(datetime.UTC)
        not_valid_after = not_valid_before + datetime.timedelta(
            days=self._agent_validity_days
        )

        server_cert = (
            x509.CertificateBuilder()
            .subject_name(csr.subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(csr.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(not_valid_before)
            .not_valid_after(not_valid_after)
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                ]),
                critical=False,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(
                    server_key.public_key()
                ),
                critical=False,
            )
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.DNSName("nats"),
                    x509.DNSName(hostname),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            )
            .sign(self._ca_key, hashes.SHA256())
        )

        logger.info(
            "certificate_generated",
            cert_type="server",
            subject=hostname,
            expiry=not_valid_after.isoformat(),
        )

        return {
            "cert": server_cert.public_bytes(
                serialization.Encoding.PEM
            ).decode("ascii"),
            "key": server_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode("ascii"),
        }

    def renew_agent_cert(self, agent_id: str) -> dict[str, str]:
        """Re-issue an agent certificate (convenience alias for issue_agent_cert).

        Logs ``certificate_renewal_completed`` with the new expiry.
        """
        result = self.issue_agent_cert(agent_id)

        # Parse expiry from the new cert for logging
        loaded = x509.load_pem_x509_certificate(
            result["cert"].encode("ascii")
        )
        logger.info(
            "certificate_renewal_completed",
            subject=agent_id,
            new_expiry=loaded.not_valid_after_utc.isoformat(),
        )
        return result


# ---------------------------------------------------------------------------
# Convenience functions — SOPS encrypt / decrypt cycle
# ---------------------------------------------------------------------------


def _find_sops_binary() -> str:
    """Resolve the SOPS binary path, or raise RuntimeError."""
    sops = shutil.which("sops")
    if sops is None:
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
        msg = (
            "SOPS binary not found. "
            "Install: brew install sops / apt install sops / "
            "download from https://github.com/getsops/sops/releases"
        )
        logger.error("certs_encrypt_failed", path=str(CERTS_YAML_PATH), error=msg)
        raise RuntimeError(msg)
    return sops


async def _run_sops(*args: str) -> tuple[int, str, str]:
    """Run ``sops <args>`` as a subprocess and return (returncode, stdout, stderr)."""
    sops_bin = _find_sops_binary()
    proc = await asyncio.create_subprocess_exec(
        sops_bin,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )


async def encrypt_certs(path: Path | None = None) -> None:
    """Encrypt ``secrets/certs.yaml`` with SOPS.

    Parameters:
        path: Path to the plaintext certs YAML file.
              Defaults to ``secrets/certs.yaml``.

    Raises:
        RuntimeError: If SOPS encryption fails.
    """
    target = Path(path) if path is not None else CERTS_YAML_PATH

    returncode, stdout, stderr = await _run_sops(
        "--encrypt", "--in-place", str(target),
    )

    if returncode != 0:
        logger.error(
            "certs_encrypt_failed",
            path=str(target),
            error=stderr.strip() or stdout.strip(),
        )
        raise RuntimeError(
            f"sops --encrypt {target} exited {returncode}: {stderr.strip()}"
        )

    logger.info("certs_encrypted", path=str(target), result="success")


async def decrypt_certs(path: Path | None = None) -> dict[str, object]:
    """Decrypt ``secrets/certs.yaml`` and return parsed YAML data.

    Parameters:
        path: Path to the encrypted certs YAML file.
              Defaults to ``secrets/certs.yaml``.

    Returns:
        Parsed YAML dict with ``ca``, ``agents`` keys.

    Raises:
        RuntimeError: If SOPS decryption fails.
        FileNotFoundError: If the certs file does not exist.
    """
    target = Path(path) if path is not None else CERTS_YAML_PATH

    if not target.exists():
        logger.error("certs_decrypt_failed", path=str(target), error="File not found")
        raise FileNotFoundError(f"Certs file not found: {target}")

    returncode, stdout, stderr = await _run_sops(
        "--decrypt", str(target),
    )

    if returncode != 0:
        logger.error(
            "certs_decrypt_failed",
            path=str(target),
            error=stderr.strip() or stdout.strip(),
        )
        raise RuntimeError(
            f"sops --decrypt {target} exited {returncode}: {stderr.strip()}"
        )

    data = yaml.safe_load(stdout)
    if not isinstance(data, dict):
        logger.error(
            "certs_decrypt_failed",
            path=str(target),
            error="Decrypted data is not a YAML mapping",
        )
        raise ValueError("Decrypted certs data is not a YAML mapping")

    logger.info("certs_decrypted", path=str(target))
    return data


async def load_certificates(
    path: Path | None = None,
) -> tuple[str, str, dict[str, dict[str, str]]]:
    """Decrypt ``secrets/certs.yaml`` and return cert data.

    Returns:
        A ``(ca_cert, ca_key, agent_certs)`` tuple where:
        - *ca_cert* is the PEM-encoded CA root certificate.
        - *ca_key* is the PEM-encoded CA root private key.
        - *agent_certs* is a dict mapping agent IDs to
          ``{"cert": <PEM>, "key": <PEM>}``.

    Raises:
        RuntimeError: If decryption fails.
        FileNotFoundError: If the certs file does not exist.
        KeyError: If required keys are missing from the YAML.
    """
    data = await decrypt_certs(path)

    ca_data = data["ca"]
    if not isinstance(ca_data, dict):
        raise KeyError("Expected 'ca' to be a mapping")

    ca_cert = ca_data["cert"]
    ca_key = ca_data["key"]
    if not isinstance(ca_cert, str) or not isinstance(ca_key, str):
        raise KeyError("Expected 'ca.cert' and 'ca.key' to be strings")

    agents_raw = data.get("agents", {})
    if not isinstance(agents_raw, dict):
        raise KeyError("Expected 'agents' to be a mapping")

    agent_certs: dict[str, dict[str, str]] = {}
    for agent_id, agent_data in agents_raw.items():
        if not isinstance(agent_data, dict):
            raise KeyError(f"Expected 'agents.{agent_id}' to be a mapping")
        agent_certs[str(agent_id)] = {
            "cert": str(agent_data["cert"]),
            "key": str(agent_data["key"]),
        }

    return ca_cert, ca_key, agent_certs


def write_temp_cert_files(
    ca_cert: str,
    ca_key: str,
    agent_certs: dict[str, dict[str, str]],
    agent_id: str | None = None,
) -> tuple[str, str, str | None, str | None]:
    """Write PEM data to temporary files for ``ssl.SSLContext`` consumption.

    Parameters:
        ca_cert: PEM-encoded CA certificate.
        ca_key: PEM-encoded CA private key.
        agent_certs: Dict of agent ID → ``{"cert": <PEM>, "key": <PEM>}``.
        agent_id: Specific agent ID to write files for.  If ``None``, only
                  the CA files are written.

    Returns:
        ``(ca_cert_path, ca_key_path, agent_cert_path, agent_key_path)``.
        Agent paths are ``None`` when *agent_id* is ``None``.
    """
    # Write CA files
    ca_cert_fd, ca_cert_path = tempfile.mkstemp(
        suffix=".pem", prefix="heretek_ca_cert_"
    )
    with os.fdopen(ca_cert_fd, "w") as f:
        f.write(ca_cert)

    ca_key_fd, ca_key_path = tempfile.mkstemp(
        suffix=".pem", prefix="heretek_ca_key_"
    )
    with os.fdopen(ca_key_fd, "w") as f:
        f.write(ca_key)

    agent_cert_path: str | None = None
    agent_key_path: str | None = None

    if agent_id is not None and agent_id in agent_certs:
        agent_data = agent_certs[agent_id]

        agent_cert_fd, agent_cert_path = tempfile.mkstemp(
            suffix=".pem", prefix=f"heretek_agent_{agent_id}_cert_"
        )
        with os.fdopen(agent_cert_fd, "w") as f:
            f.write(agent_data["cert"])

        agent_key_fd, agent_key_path = tempfile.mkstemp(
            suffix=".pem", prefix=f"heretek_agent_{agent_id}_key_"
        )
        with os.fdopen(agent_key_fd, "w") as f:
            f.write(agent_data["key"])

    logger.debug(
        "temp_cert_files_written",
        ca_cert_path=ca_cert_path,
        ca_key_path=ca_key_path,
        agent_cert_path=agent_cert_path,
        agent_key_path=agent_key_path,
    )

    return ca_cert_path, ca_key_path, agent_cert_path, agent_key_path


def _check_renewal(agent_certs: dict[str, dict[str, str]]) -> None:
    """Check all agent certs for pending expiry and log warnings."""
    for agent_id, certs in agent_certs.items():
        try:
            cert = x509.load_pem_x509_certificate(
                certs["cert"].encode("ascii")
            )
            remaining = (
                cert.not_valid_after_utc
                - datetime.datetime.now(datetime.UTC)
            ).days
            if remaining <= RENEWAL_THRESHOLD_DAYS:
                logger.warning(
                    "certificate_renewal_needed",
                    days_remaining=remaining,
                    subject=agent_id,
                )
        except Exception as exc:
            logger.warning(
                "cert_parse_warning",
                agent_id=agent_id,
                error=str(exc),
            )


def generate_cert_files(
    output_dir: Path,
    ca: CertificateAuthority | None = None,
) -> dict[str, Path]:
    """Generate CA, server, and agent certificates and write them to *output_dir*.

    Creates:
        - ``ca.crt`` — CA root certificate
        - ``ca.key`` — CA root private key
        - ``nats-server.crt`` — server certificate
        - ``nats-server.key`` — server private key
        - ``agent.crt`` — default agent certificate
        - ``agent.key`` — default agent private key

    Parameters:
        output_dir: Directory to write PEM files into (created if missing).
        ca: Optional pre-existing CA.  Created fresh when ``None``.

    Returns:
        A dict mapping descriptive key → absolute path to the written file.
    """
    if ca is None:
        ca = CertificateAuthority()

    output_dir.mkdir(parents=True, exist_ok=True)

    # Write CA files
    ca_cert_path = output_dir / "ca.crt"
    ca_cert_path.write_text(ca.ca_cert_pem, encoding="ascii")
    ca_key_path = output_dir / "ca.key"
    ca_key_path.write_text(ca.ca_key_pem, encoding="ascii")

    # Issue & write server cert
    server_material = ca.issue_server_cert()
    server_cert_path = output_dir / "nats-server.crt"
    server_cert_path.write_text(server_material["cert"], encoding="ascii")
    server_key_path = output_dir / "nats-server.key"
    server_key_path.write_text(server_material["key"], encoding="ascii")

    # Issue & write agent cert
    agent_material = ca.issue_agent_cert("heretek-api")
    agent_cert_path = output_dir / "agent.crt"
    agent_cert_path.write_text(agent_material["cert"], encoding="ascii")
    agent_key_path = output_dir / "agent.key"
    agent_key_path.write_text(agent_material["key"], encoding="ascii")

    logger.info(
        "cert_files_generated",
        output_dir=str(output_dir),
        files=[
            str(p.name)
            for p in (
                ca_cert_path,
                ca_key_path,
                server_cert_path,
                server_key_path,
                agent_cert_path,
                agent_key_path,
            )
        ],
    )

    return {
        "ca_cert": ca_cert_path,
        "ca_key": ca_key_path,
        "server_cert": server_cert_path,
        "server_key": server_key_path,
        "agent_cert": agent_cert_path,
        "agent_key": agent_key_path,
    }


async def check_and_renew_certs(
    certs_path: Path | None = None,
) -> bool:
    """Check agent certificate expiry and renew if near expiration.

    Called at startup after SecretsLoader.  Decrypts ``secrets/certs.yaml``,
    inspects the agent cert ``not_valid_after_utc``, and when fewer than
    ``RENEWAL_THRESHOLD_DAYS`` remain:

    1. Logs ``certificate_renewal_needed`` with *days_remaining*.
    2. Calls ``CertificateAuthority.renew_agent_cert()`` to regenerate.
    3. SOPS-encrypts the updated ``secrets/certs.yaml``.
    4. Logs ``certificate_renewal_completed``.

    When ``SOPS_AGE_KEY`` is unavailable (common in unconfigured dev
    environments), the function skips renewal with a warning.

    Parameters:
        certs_path: Path to the encrypted certs YAML file.
                    Defaults to ``secrets/certs.yaml``.

    Returns:
        ``True`` when renewal was performed, ``False`` otherwise.
    """
    target = Path(certs_path) if certs_path is not None else CERTS_YAML_PATH

    if not target.exists():
        logger.info(
            "cert_renewal_skipped",
            reason="certs_file_not_found",
            path=str(target),
        )
        return False

    # Check SOPS availability
    sops_key = os.environ.get("SOPS_AGE_KEY")
    if not sops_key:
        logger.warning(
            "cert_renewal_skipped",
            reason="SOPS_AGE_KEY not set — cannot decrypt or re-encrypt certs",
        )
        return False

    try:
        # Decrypt existing certs
        data = await decrypt_certs(target)
    except Exception as exc:
        logger.warning(
            "cert_renewal_skipped",
            reason="decrypt_failed",
            error=str(exc),
        )
        return False

    # Find the first agent cert entry
    agents = data.get("agents", {})
    if not isinstance(agents, dict) or not agents:
        logger.info(
            "cert_renewal_skipped",
            reason="no_agent_certs_found",
        )
        return False

    # Pick the first agent entry (or "heretek-api" if present)
    agent_id, agent_data = ("heretek-api", agents.get("heretek-api"))
    if agent_data is None:
        agent_id, agent_data = next(iter(agents.items()))
    if not isinstance(agent_data, dict):
        logger.warning(
            "cert_renewal_skipped",
            reason="agent_data_not_a_mapping",
        )
        return False

    # Check expiry
    try:
        cert = x509.load_pem_x509_certificate(
            str(agent_data["cert"]).encode("ascii")
        )
        remaining = (
            cert.not_valid_after_utc
            - datetime.datetime.now(datetime.UTC)
        ).days
    except Exception as exc:
        logger.warning(
            "cert_renewal_skipped",
            reason="cert_parse_failed",
            error=str(exc),
        )
        return False

    if remaining > RENEWAL_THRESHOLD_DAYS:
        logger.info(
            "cert_renewal_not_needed",
            subject=agent_id,
            days_remaining=remaining,
            threshold_days=RENEWAL_THRESHOLD_DAYS,
        )
        return False

    # Renewal needed
    logger.warning(
        "certificate_renewal_needed",
        days_remaining=remaining,
        subject=agent_id,
    )

    try:
        ca_data = data.get("ca", {})
        if not isinstance(ca_data, dict):
            logger.error("cert_renewal_failed", reason="ca_data_not_a_mapping")
            return False

        ca = CertificateAuthority(
            common_name=CA_CN,
            key_size=CA_KEY_SIZE,
            validity_days=CA_VALIDITY_DAYS,
            agent_key_size=AGENT_KEY_SIZE,
            agent_validity_days=AGENT_VALIDITY_DAYS,
        )

        # Re-issue the agent cert (renew_agent_cert logs certificate_renewal_completed)
        new_agent = ca.renew_agent_cert(agent_id)

        # Also re-issue server cert
        ca.issue_server_cert()

        # Update the in-memory data
        data["agents"][agent_id] = {"cert": new_agent["cert"], "key": new_agent["key"]}
        data["ca"] = {"cert": ca.ca_cert_pem, "key": ca.ca_key_pem}

        # Write plaintext back temporarily so SOPS can encrypt
        plaintext_path = target.with_suffix(".renewal.yaml")
        try:
            plaintext_path.write_text(
                yaml.dump(data, default_flow_style=False), encoding="utf-8"
            )
            await encrypt_certs(plaintext_path)
            # Move encrypted result over the original
            shutil.move(str(plaintext_path), str(target))
        finally:
            if plaintext_path.exists():
                plaintext_path.unlink(missing_ok=True)

        return True

    except Exception as exc:
        logger.error(
            "cert_renewal_failed",
            subject=agent_id,
            error=str(exc),
        )
        return False
