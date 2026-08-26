"""SoAI - Anonymous owner tokens for OpenAI-compatible endpoints [backend/core/openai/anonymous_owner_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets

from core.errors.exceptions import StateError

__all__ = (
    "generate_anonymous_owner_token",
    "normalize_anonymous_owner_token",
)


def normalize_anonymous_owner_token(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip()
    if len(token) < 22 or len(token) > 256:
        return None
    for char in token:
        if char.isascii() and char.isalnum():
            continue
        if char in {"-", "_"}:
            continue
        return None
    return token or None


def generate_anonymous_owner_token() -> str:
    token = secrets.token_urlsafe(32)
    normalized = normalize_anonymous_owner_token(token)
    if normalized is None:
        raise StateError("Generated anonymous owner token is invalid.")
    return normalized
