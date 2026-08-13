"""APK signing-scheme and certificate-chain extraction.

Supports APK Signature Scheme **v1 (JAR)**, **v2**, and **v3** via
androguard. v4 support requires ``apksig`` from the Android SDK and is
deferred to a future phase.

The :class:`CertificateInfo` dataclass is a JSON-serializable view of a
single X.509 certificate in the APK's signing chain.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .apk import Apk
from .errors import APKInvalid, APKNotFound

try:
    from androguard.core.apk import APK
    from asn1crypto import x509 as asn1_x509  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "androguard and asn1crypto are required for android_re_core.certs. "
        "Install with: uv pip install 'androguard==4.1.4' asn1crypto"
    ) from e


__all__ = [
    "CertificateInfo",
    "CertsView",
    "SignatureInfo",
    "SignerInfo",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SignerInfo:
    """Information about a single APK signature scheme signer."""

    signer_index: int
    signer_name: str
    signature_versions: tuple[int, ...]  # 1, 2, 3
    v1_digest_alg: str | None = None
    v2_digest_alg: str | None = None
    v3_digest_alg: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "signer_index": self.signer_index,
            "signer_name": self.signer_name,
            "signature_versions": list(self.signature_versions),
            "v1_digest_alg": self.v1_digest_alg,
            "v2_digest_alg": self.v2_digest_alg,
            "v3_digest_alg": self.v3_digest_alg,
        }


@dataclass(frozen=True)
class SignatureInfo:
    """Top-level summary of an APK's signature state."""

    is_signed: bool
    signers: tuple[SignerInfo, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_signed": self.is_signed,
            "signers": [s.to_dict() for s in self.signers],
        }


@dataclass(frozen=True)
class CertificateInfo:
    """A single X.509 certificate in the APK's signing chain."""

    subject: str
    issuer: str
    serial: str
    not_valid_before: datetime
    not_valid_after: datetime
    signature_algorithm: str
    public_key_algorithm: str
    public_key_size: int
    fingerprint_sha256: str
    is_self_signed: bool
    is_expired: bool
    is_not_yet_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "issuer": self.issuer,
            "serial": self.serial,
            "not_valid_before": self.not_valid_before.isoformat(),
            "not_valid_after": self.not_valid_after.isoformat(),
            "signature_algorithm": self.signature_algorithm,
            "public_key_algorithm": self.public_key_algorithm,
            "public_key_size": self.public_key_size,
            "fingerprint_sha256": self.fingerprint_sha256,
            "is_self_signed": self.is_self_signed,
            "is_expired": self.is_expired,
            "is_not_yet_valid": self.is_not_yet_valid,
        }


# ---------------------------------------------------------------------------
# CertsView
# ---------------------------------------------------------------------------


class CertsView:
    """Typed view over an APK's signature and certificate chain."""

    def __init__(
        self,
        signature: SignatureInfo,
        certificates: list[CertificateInfo],
    ) -> None:
        self.signature = signature
        self.certificates = certificates

    @classmethod
    def from_apk(cls, apk: Apk) -> CertsView:
        """Build a :class:`CertsView` from an :class:`Apk`."""
        if apk.is_closed:
            raise APKInvalid("APK has been closed")
        raw = apk.raw
        sig_info = _extract_signature(raw)
        certs: list[CertificateInfo] = []
        for idx in range(len(sig_info.signers)):
            try:
                certs.extend(_extract_certs(raw, idx))
            except (APKNotFound, ValueError):
                continue
        return cls(signature=sig_info, certificates=certs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signature": self.signature.to_dict(),
            "certificates": [c.to_dict() for c in self.certificates],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_signature(apk: APK) -> SignatureInfo:
    """Walk androguard's signature APIs to produce a :class:`SignatureInfo`."""
    is_signed = apk.is_signed()
    if not is_signed:
        return SignatureInfo(is_signed=False, signers=())

    # v1: list of (name, digest) tuples via get_signature_name() / get_issuer()
    # v2/v3: get_apk_signing_block() returns raw bytes; we report "present"
    # rather than decoding the block (androguard 4.1.4 does not expose
    # a typed view for v2/v3).
    signers: list[SignerInfo] = []
    for idx, name in enumerate(apk.get_signature_names() or []):
        versions: list[int] = []
        if apk.get_signature_name(idx) is not None:
            versions.append(1)
        # androguard exposes v2/v3 presence via get_apk_signing_block() which
        # returns bytes if present and None otherwise.
        try:
            block = apk.get_apk_signing_block()
        except Exception:
            block = None
        if block:
            versions.append(2)
            # v3 has the same block format; check via get_apk_v3_signing_block
            # if androguard exposes it (defensive).
            if hasattr(apk, "get_apk_v3_signing_block"):
                try:
                    if apk.get_apk_v3_signing_block() is not None:  # type: ignore[attr-defined]
                        versions.append(3)
                except Exception:
                    pass

        signers.append(
            SignerInfo(
                signer_index=idx,
                signer_name=name,
                signature_versions=tuple(versions) or (1,),
            )
        )

    return SignatureInfo(is_signed=True, signers=tuple(signers))


def _extract_certs(apk: APK, signer_index: int) -> list[CertificateInfo]:
    """Extract the certificate chain for a given signer.

    Uses androguard's :meth:`get_certificates` (v1 JAR signing). For
    v2/v3 we fall back to the v1 certificates, since the chain in v1 is
    the same as in v2/v3.
    """
    out: list[CertificateInfo] = []
    certs = apk.get_certificates(signer_index) or []
    for cert in certs:
        out.append(_cert_to_info(cert))
    return out


def _cert_to_info(cert: Any) -> CertificateInfo:
    """Convert an androguard certificate object to a :class:`CertificateInfo`."""
    # androguard 4.x returns asn1crypto.x509.Certificate objects from
    # get_certificates(). If we get cryptography.x509 instead, dispatch.
    if hasattr(cert, "tbs_certificate"):
        return _from_asn1(cert)
    if hasattr(cert, "public_bytes"):
        return _from_cryptography(cert)
    raise APKInvalid(f"Unsupported certificate type: {type(cert).__name__}")


def _from_asn1(cert: asn1_x509.Certificate) -> CertificateInfo:
    """Build a :class:`CertificateInfo` from an asn1crypto cert."""
    subject = cert.subject.human_friendly
    issuer = cert.issuer.human_friendly
    serial = format_serial(cert.serial_number)
    nb = cert.not_valid_before
    na = cert.not_valid_after
    sig_algo = cert.signature_algo
    pubkey = cert.public_key

    # asn1crypto returns algorithm names like "sha256_rsa"; normalize.
    sig_algo_str = sig_algo.upper().replace("_", " with ") if sig_algo else "unknown"
    pub_algo = pubkey.algorithm.upper() if pubkey.algorithm else "unknown"
    pub_size = pubkey.bit_size if hasattr(pubkey, "bit_size") else 0

    der = cert.dump()
    fingerprint = hashlib.sha256(der).hexdigest()

    now = datetime.now(tz=UTC)
    is_expired = na < now
    is_not_yet_valid = nb > now
    is_self_signed = cert.subject == cert.issuer

    return CertificateInfo(
        subject=subject,
        issuer=issuer,
        serial=serial,
        not_valid_before=nb.replace(tzinfo=UTC),
        not_valid_after=na.replace(tzinfo=UTC),
        signature_algorithm=sig_algo_str,
        public_key_algorithm=pub_algo,
        public_key_size=pub_size,
        fingerprint_sha256=fingerprint,
        is_self_signed=is_self_signed,
        is_expired=is_expired,
        is_not_yet_valid=is_not_yet_valid,
    )


def _from_cryptography(cert: Any) -> CertificateInfo:
    """Build a :class:`CertificateInfo` from a ``cryptography.x509`` cert."""
    from cryptography.hazmat.primitives import serialization  # type: ignore[import-untyped]
    from cryptography.x509 import Name  # type: ignore[import-untyped]

    subject = cert.subject.rfc4514_string() if isinstance(cert.subject, Name) else str(cert.subject)
    issuer = cert.issuer.rfc4514_string() if isinstance(cert.issuer, Name) else str(cert.issuer)
    serial = format_serial(cert.serial_number)
    nb = cert.not_valid_before_utc
    na = cert.not_valid_after_utc
    sig_algo = cert.signature_algorithm_oid._name  # type: ignore[attr-defined]
    pubkey = cert.public_key()
    pub_algo = type(pubkey).__name__
    pub_size = getattr(pubkey, "key_size", 0) or 0
    der = cert.public_bytes(serialization.Encoding.DER)
    fingerprint = hashlib.sha256(der).hexdigest()
    now = datetime.now(tz=UTC)
    return CertificateInfo(
        subject=subject,
        issuer=issuer,
        serial=serial,
        not_valid_before=nb,
        not_valid_after=na,
        signature_algorithm=sig_algo or "unknown",
        public_key_algorithm=pub_algo,
        public_key_size=pub_size,
        fingerprint_sha256=fingerprint,
        is_self_signed=cert.subject == cert.issuer,
        is_expired=na < now,
        is_not_yet_valid=nb > now,
    )


def format_serial(serial: int) -> str:
    """Format a certificate serial number as a hex string with colons."""
    hex_str = format(serial, "x")
    # Group by 2 chars
    return ":".join(hex_str[i : i + 2].upper() for i in range(0, len(hex_str), 2))
