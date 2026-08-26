"""SoAI - Password vault encryption helpers [backend/database/repositories/users/password_vault_crypto.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from cryptography.fernet import Fernet

from core.security.secret_crypto import (
    decrypt_optional_secret,
    decrypt_required_secret,
    encrypt_optional_secret,
    encrypt_required_secret,
)

__all__ = (
    "decrypt_optional",
    "decrypt_required",
    "encrypt_optional",
    "encrypt_required",
    "mask_username",
)


def mask_username(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    at_index = normalized.find("@")
    if 0 < at_index < len(normalized) - 1:
        local_part = normalized[:at_index]
        domain_part = normalized[at_index + 1 :]
        local_first = local_part[0]
        domain_first = domain_part[0]
        last_dot = domain_part.rfind(".")
        suffix = ""
        if 0 < last_dot < len(domain_part) - 1:
            candidate_suffix = domain_part[last_dot + 1 :]
            if 1 <= len(candidate_suffix) <= 6:
                suffix = f".{candidate_suffix}"
        return f"{local_first}***@{domain_first}***{suffix}".lower()
    first_char = normalized[0]
    return f"{first_char}***".lower()


def encrypt_required(fernets: tuple[Fernet, ...], plaintext: str) -> str:
    return encrypt_required_secret(
        fernets,
        plaintext,
        label="password vault secret value",
    )


def encrypt_optional(fernets: tuple[Fernet, ...], plaintext: str | None) -> str | None:
    if not isinstance(plaintext, str) or not plaintext.strip():
        return None
    return encrypt_optional_secret(
        fernets,
        plaintext,
        label="password vault secret value",
    )


def decrypt_required(fernets: tuple[Fernet, ...], encrypted: str | None) -> str:
    return decrypt_required_secret(
        fernets,
        encrypted,
        label="password vault encrypted value",
    )


def decrypt_optional(fernets: tuple[Fernet, ...], encrypted: str | None) -> str | None:
    return decrypt_optional_secret(
        fernets,
        encrypted,
        label="password vault secret",
    )
