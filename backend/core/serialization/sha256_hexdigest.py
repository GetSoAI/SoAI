"""SoAI - Canonical SHA-256 hexadecimal digest validation [backend/core/serialization/sha256_hexdigest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError

__all__ = ("is_canonical_sha256_hexdigest", "require_canonical_sha256_hexdigest")


def is_canonical_sha256_hexdigest(value: str) -> bool:
    return (
        len(value) == 64
        and value == value.strip()
        and value == value.lower()
        and all(char in "0123456789abcdef" for char in value)
    )


def require_canonical_sha256_hexdigest(value: str, *, label: str) -> str:
    if not isinstance(value, str):
        raise StateError(f"{label} must be a string.")
    if value != value.strip():
        raise StateError(f"{label} must not contain leading/trailing whitespace.")
    if len(value) != 64:
        raise StateError(f"{label} must be a 64-character lowercase sha256 hex digest.")
    if value != value.lower():
        raise StateError(f"{label} must be a lowercase sha256 hex digest.")
    for char in value:
        if char not in "0123456789abcdef":
            raise StateError(f"{label} contains a non-hex character.")
    return value
