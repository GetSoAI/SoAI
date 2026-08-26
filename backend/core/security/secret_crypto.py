"""SoAI - Strict secret encryption and decryption helpers [backend/core/security/secret_crypto.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence

from cryptography.fernet import Fernet

from core.errors.exceptions import StateError, ValidationError
from core.security.encryption import decrypt_data, encrypt_data
from core.types.json import JSONValue

__all__ = (
    "coerce_optional_secret_plaintext",
    "decrypt_optional_secret",
    "decrypt_required_secret",
    "encrypt_optional_secret",
    "encrypt_required_secret",
)


def coerce_optional_secret_plaintext(
    value: JSONValue | str | None,
    *,
    label: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a string or null.")
    if value == "" or not value.strip():
        return None
    return value


def encrypt_required_secret(fernets: Sequence[Fernet], plaintext: str, *, label: str) -> str:
    if not isinstance(plaintext, str) or plaintext == "":
        raise ValidationError(f"{label} must not be empty.")
    encrypted = encrypt_data(fernets, plaintext)
    if not encrypted:
        raise StateError(f"Failed to encrypt {label}.")
    return encrypted


def encrypt_optional_secret(
    fernets: Sequence[Fernet],
    plaintext: str | None,
    *,
    label: str,
) -> str | None:
    if plaintext is None:
        return None
    if not isinstance(plaintext, str):
        raise ValidationError(f"{label} must be a string or null.")
    if plaintext == "":
        return None
    encrypted = encrypt_data(fernets, plaintext)
    if not encrypted:
        raise StateError(f"Failed to encrypt {label}.")
    return encrypted


def decrypt_required_secret(
    fernets: Sequence[Fernet],
    encrypted: str | None,
    *,
    label: str,
) -> str:
    if not encrypted:
        raise StateError(f"{label} is missing.")
    decrypted = decrypt_data(fernets, encrypted)
    if decrypted is None:
        raise StateError(f"Failed to decrypt {label}.")
    return decrypted


def decrypt_optional_secret(
    fernets: Sequence[Fernet],
    encrypted: str | None,
    *,
    label: str,
) -> str | None:
    if not encrypted:
        return None
    decrypted = decrypt_data(fernets, encrypted)
    if decrypted is None:
        raise StateError(f"Failed to decrypt {label}.")
    return decrypted
