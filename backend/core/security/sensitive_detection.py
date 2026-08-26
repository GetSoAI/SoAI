"""SoAI - Sensitive key and value detection helpers [backend/core/security/sensitive_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

__all__ = (
    "SENSITIVE_VALUE_PATTERN_TEXTS",
    "is_sensitive_key_name",
    "looks_like_sensitive_string",
)

SENSITIVE_VALUE_PATTERN_TEXTS: tuple[str, ...] = (
    "\\bsoai-[A-Za-z0-9_-]{20,}\\b",
    "\\bsk-[A-Za-z0-9_-]{20,}\\b",
    "\\bpk-[A-Za-z0-9_-]{20,}\\b",
    "(?i)\\bbearer\\s+[A-Za-z0-9._-]{20,}",
    "^[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{0,}$",
)
_SENSITIVE_TOKENS: frozenset[str] = frozenset(
    {
        "token",
        "secret",
        "password",
        "credential",
        "bearer",
        "authorization",
        "jwt",
    },
)
_SENSITIVE_COMPACT_KEYS: frozenset[str] = frozenset(
    {
        "accesskeyid",
        "secretaccesskey",
        "clientsecret",
        "accesstoken",
        "refreshtoken",
        "idtoken",
        "apikey",
    },
)


def looks_like_sensitive_string(value: str) -> bool:
    for pattern_text in SENSITIVE_VALUE_PATTERN_TEXTS:
        if re.search(pattern_text, value):
            return True
    return False


def is_sensitive_key_name(key: str, *, include_credential_containers: bool = False) -> bool:
    key_raw = str(key or "").strip()
    key_lower = key_raw.lower()
    if not key_lower:
        return False
    if key_lower == "context_window_tokens":
        return False
    compact = re.sub(r"[^a-z0-9]+", "", key_lower)
    if compact == "auth":
        return True
    if compact == "credentials":
        return include_credential_containers
    if "credential" in compact:
        return True
    if compact in _SENSITIVE_COMPACT_KEYS:
        return True
    with_boundaries = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key_raw)
    with_boundaries = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", with_boundaries)
    tokens = [token for token in re.split(r"[^a-z0-9]+", with_boundaries.lower()) if token]
    if any(token in _SENSITIVE_TOKENS for token in tokens):
        return True
    if "api" in tokens and "key" in tokens:
        return True
    if tokens and tokens[-1] == "key":
        return True
    if "private" in tokens and "key" in tokens:
        return True
    if "encryption" in tokens and "key" in tokens:
        return True
    if "client" in tokens and "secret" in tokens:
        return True
    if "access" in tokens and "key" in tokens:
        return True
    return False
