"""SoAI - TLS certificate and key lifecycle helpers [backend/features/api/middleware/tls_certificates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ipaddress
import os
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.types import (
    PrivateKeyTypes,
    PublicKeyTypes,
)
from cryptography.x509.oid import NameOID

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ConfigurationError, ValidationError
from core.filesystem.atomic_binary_writes import atomic_write_binary_content
from core.filesystem.open_files import open_binary
from core.logging.trace import get_logger
from core.platform.os import is_windows
from core.timing.formatting import utc_now

__all__ = (
    "ensure_auto_certificate",
    "validate_user_certificate",
)

LOGGER_NAME = "SoAI.features.api.tls_certificates"
OPERATION_API_MIDDLEWARE_TLS_ENSURE_PRIVATE_DIR = "api_middleware.tls.ensure_private_dir"


def _is_pem_private_key_encrypted(key_data: bytes) -> bool:
    header = key_data.lstrip()[:400]
    return (
        b"BEGIN ENCRYPTED PRIVATE KEY" in header
        or b"Proc-Type: 4,ENCRYPTED" in header
        or b"DEK-Info:" in header
    )


_DEFAULT_CERT_FILENAME = "soai-selfsigned.crt"
_DEFAULT_KEY_FILENAME = "soai-selfsigned.key"
_DEFAULT_CERT_DIR = "~/.soai/certs"
_CERT_VALIDITY_DAYS = 365
_CERT_RENEWAL_THRESHOLD_DAYS = 14


def _ensure_private_dir(path: str) -> None:
    os.makedirs(path, mode=0o700, exist_ok=True)
    if is_windows():
        return
    try:
        os.chmod(path, 0o700)
    except OSError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to set TLS cert directory permissions (non-critical).",
            operation=OPERATION_API_MIDDLEWARE_TLS_ENSURE_PRIVATE_DIR,
            details={"path": path},
            level="debug",
        )


def _default_cert_paths() -> tuple[str, str]:
    cert_dir = os.path.abspath(os.path.expanduser(os.fspath(_DEFAULT_CERT_DIR)))
    _ensure_private_dir(cert_dir)
    return (
        os.path.join(cert_dir, _DEFAULT_CERT_FILENAME),
        os.path.join(cert_dir, _DEFAULT_KEY_FILENAME),
    )


def _load_pem_certificate(path: str) -> x509.Certificate:
    with open_binary(path, mode="rb") as handle:
        data = handle.read()
    return x509.load_pem_x509_certificate(data)


def _load_private_key(path: str | os.PathLike[str], password: str | None) -> PrivateKeyTypes:
    with open_binary(path, mode="rb") as handle:
        key_data = handle.read()
    encrypted = _is_pem_private_key_encrypted(key_data)
    if encrypted and not password:
        raise ConfigurationError("TLS private key is encrypted but no password was provided.")
    key_password = password.encode() if encrypted and password else None
    try:
        return serialization.load_pem_private_key(key_data, password=key_password)
    except (TypeError, ValueError) as exception:
        raise ConfigurationError(
            "Failed to load TLS private key. Verify key format and password.",
        ) from exception


def _keys_match(certificate: x509.Certificate, private_key: PrivateKeyTypes) -> bool:
    public_key: PublicKeyTypes = certificate.public_key()
    try:
        cert_public_bytes = public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        private_public_key = private_key.public_key()
        private_public_bytes = private_public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return cert_public_bytes == private_public_bytes


def _certificate_needs_renewal(certificate: x509.Certificate) -> bool:
    now = utc_now()
    renew_after = now + timedelta(days=_CERT_RENEWAL_THRESHOLD_DAYS)
    return _certificate_not_after(certificate) <= renew_after


def _certificate_not_after(certificate: x509.Certificate) -> datetime:
    return certificate.not_valid_after_utc


def _generate_self_signed_certificate(
    cert_path: str,
    key_path: str,
    validity_days: int = _CERT_VALIDITY_DAYS,
) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "SoAI Local Service"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SoAI"),
        ],
    )
    now = utc_now()
    alt_names = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ]
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    key_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_bytes = certificate.public_bytes(serialization.Encoding.PEM)
    cert_mode = None if is_windows() else 0o644
    key_mode = None if is_windows() else 0o600
    atomic_write_binary_content(cert_path, cert_bytes, file_mode=cert_mode)
    atomic_write_binary_content(key_path, key_bytes, file_mode=key_mode)


def ensure_auto_certificate(password: str | None) -> tuple[str, str]:
    cert_path, key_path = _default_cert_paths()
    if os.path.exists(cert_path) and os.path.exists(key_path):
        certificate = _load_pem_certificate(cert_path)
        private_key = _load_private_key(key_path, password)
        if not _keys_match(certificate, private_key) or _certificate_needs_renewal(certificate):
            _generate_self_signed_certificate(cert_path, key_path)
            certificate = _load_pem_certificate(cert_path)
            private_key = _load_private_key(key_path, password)
        if _certificate_not_after(certificate) <= utc_now():
            _generate_self_signed_certificate(cert_path, key_path)
    else:
        _generate_self_signed_certificate(cert_path, key_path)
    return (cert_path, key_path)


def validate_user_certificate(cert_path: str, key_path: str, password: str | None) -> None:
    if not os.path.exists(cert_path):
        raise ConfigurationError(f"Configured certificate file not found: {cert_path}")
    if not os.path.exists(key_path):
        raise ConfigurationError(f"Configured key file not found: {key_path}")
    certificate = _load_pem_certificate(cert_path)
    private_key = _load_private_key(key_path, password)
    if _certificate_not_after(certificate) <= utc_now():
        raise ValidationError("Configured TLS certificate is expired.")
    if not _keys_match(certificate, private_key):
        raise ValidationError("Configured TLS certificate does not match the provided key.")
