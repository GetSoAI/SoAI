"""SoAI - WebUI CSRF token operations [backend/core/auth/csrf_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
import secrets

from core.errors.exceptions import StateError
from core.serialization.base64_values import encode_base64_urlsafe_ascii

__all__ = (
    "SOAI_CSRF_HEADER_NAME",
    "create_csrf_token",
    "csrf_cookie_is_valid",
    "csrf_header_matches_cookie",
)

SOAI_CSRF_HEADER_NAME = "X-SoAI-CSRF"
_CSRF_DERIVATION_NAMESPACE = "soai-csrf-token-v1"
_CSRF_TOKEN_SEPARATOR = "."


def _sign_csrf_nonce(nonce: str, *, secret_key: str) -> str:
    if not secret_key:
        raise StateError("CSRF token secret key is not configured.")
    payload = f"{_CSRF_DERIVATION_NAMESPACE}:{nonce}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def create_csrf_token(secret_key: str) -> str:
    nonce = encode_base64_urlsafe_ascii(secrets.token_bytes(32), strip_padding=True)
    signature = _sign_csrf_nonce(nonce, secret_key=secret_key)
    return f"{nonce}{_CSRF_TOKEN_SEPARATOR}{signature}"


def _split_csrf_token(value: str | None) -> tuple[str, str] | None:
    token = str(value or "").strip()
    if not token:
        return None
    parts = token.split(_CSRF_TOKEN_SEPARATOR)
    if len(parts) != 2:
        return None
    nonce, signature = parts
    if not nonce or not signature:
        return None
    return (nonce, signature)


def csrf_cookie_is_valid(
    cookie_value: str | None,
    *,
    secret_keys: tuple[str, ...],
) -> bool:
    parts = _split_csrf_token(cookie_value)
    if parts is None:
        return False
    nonce, signature = parts
    valid = False
    for secret_key in secret_keys:
        expected = _sign_csrf_nonce(nonce, secret_key=secret_key)
        valid = secrets.compare_digest(signature, expected) or valid
    return valid


def csrf_header_matches_cookie(
    cookie_value: str | None,
    header_value: str | None,
    *,
    secret_keys: tuple[str, ...],
) -> bool:
    cookie_token = str(cookie_value or "").strip()
    header_token = str(header_value or "").strip()
    if not cookie_token or not header_token:
        return False
    if not secrets.compare_digest(cookie_token, header_token):
        return False
    return csrf_cookie_is_valid(cookie_token, secret_keys=secret_keys)
