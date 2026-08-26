"""SoAI - TLS configuration and self-signed certificate generation for API [backend/features/api/middleware/tls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import ssl
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ConfigurationError, ValidationError
from core.security.tls_policy import SERVER_TLS12_AEAD_CIPHERS
from core.validation.boolean_coercion import coerce_bool_with_default
from features.api.middleware.tls_certificates import (
    ensure_auto_certificate,
    validate_user_certificate,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = ("prepare_tls_configuration",)


def prepare_tls_configuration(config: ConfigProtocol) -> tuple[dict[str, str | int], bool]:
    tls_enabled_raw = config.get("SERVER.HTTP.SSL.TLS_ENABLED")
    tls_enabled = _coerce_config_bool(tls_enabled_raw, False)
    if not tls_enabled:
        return ({}, False)
    cert_file = config.get("SERVER.HTTP.SSL.CERT_FILE")
    key_file = config.get("SERVER.HTTP.SSL.KEY_FILE")
    ca_file = config.get("SERVER.HTTP.SSL.CA_FILE")
    key_password_raw = config.get("SERVER.HTTP.SSL.KEY_PASSWORD")
    key_password: str | None = str(key_password_raw) if isinstance(key_password_raw, str) else None
    tls_options: dict[str, str | int] = {
        "ssl_ciphers": SERVER_TLS12_AEAD_CIPHERS,
    }
    is_user_supplied = False
    if any((ca_file, key_password)) and (not (cert_file and key_file)):
        raise ValidationError("TLS CA file or key password provided without certificate and key.")
    if cert_file or key_file:
        if not cert_file or not key_file:
            raise ValidationError(
                "Both SERVER.HTTP.SSL.CERT_FILE and SERVER.HTTP.SSL.KEY_FILE are required for TLS.",
            )
        cert_path = os.path.abspath(os.path.expanduser(str(cert_file)))
        key_path = os.path.abspath(os.path.expanduser(str(key_file)))
        validate_user_certificate(cert_path, key_path, key_password)
        tls_options["ssl_certfile"] = cert_path
        tls_options["ssl_keyfile"] = key_path
        if key_password:
            tls_options["ssl_keyfile_password"] = key_password
        if ca_file:
            ca_path = os.path.abspath(os.path.expanduser(str(ca_file)))
            if not os.path.exists(ca_path):
                raise ConfigurationError(f"Configured TLS CA file not found: {ca_path}")
            tls_options["ssl_ca_certs"] = ca_path
            tls_options["ssl_cert_reqs"] = ssl.CERT_REQUIRED
        is_user_supplied = True
    else:
        cert_path, key_path = ensure_auto_certificate(key_password)
        tls_options["ssl_certfile"] = cert_path
        tls_options["ssl_keyfile"] = key_path
    return (tls_options, is_user_supplied)


def _coerce_config_bool(value: ConfigValue | None, default: bool) -> bool:
    if value is None or isinstance(value, str | int | float | bool):
        return coerce_bool_with_default(value, default=default, strict=False)
    return default
