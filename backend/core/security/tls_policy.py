"""SoAI - Server TLS protocol and cipher hardening policy [backend/core/security/tls_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import ssl

from core.meta.paths import join_data_abs
from core.platform.os import is_windows

__all__ = (
    "SERVER_TLS12_AEAD_CIPHERS",
    "apply_server_tls_policy",
    "resolve_account_auto_tls_certificate_paths",
    "resolve_auto_tls_certificate_paths",
)

_DEFAULT_CERT_DIR = "~/.soai/certs"
_CERTIFICATE_FILE_NAME = "soai-selfsigned.crt"
_KEY_FILE_NAME = "soai-selfsigned.key"

SERVER_TLS12_AEAD_CIPHERS = (
    "ECDHE-ECDSA-AES256-GCM-SHA384:"
    "ECDHE-RSA-AES256-GCM-SHA384:"
    "ECDHE-ECDSA-AES128-GCM-SHA256:"
    "ECDHE-RSA-AES128-GCM-SHA256:"
    "ECDHE-ECDSA-CHACHA20-POLY1305:"
    "ECDHE-RSA-CHACHA20-POLY1305"
)


def _certificate_paths(directory: str) -> tuple[str, str]:
    return (
        os.path.join(directory, _CERTIFICATE_FILE_NAME),
        os.path.join(directory, _KEY_FILE_NAME),
    )


def resolve_account_auto_tls_certificate_paths() -> tuple[str, str]:
    return _certificate_paths(os.path.abspath(os.path.expanduser(os.fspath(_DEFAULT_CERT_DIR))))


def resolve_auto_tls_certificate_paths(base_dir: str) -> tuple[str, str]:
    if is_windows():
        return _certificate_paths(join_data_abs(base_dir, "state", "certs"))
    return resolve_account_auto_tls_certificate_paths()


def apply_server_tls_policy(context: ssl.SSLContext) -> ssl.SSLContext:
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.options |= ssl.OP_NO_COMPRESSION
    return context
