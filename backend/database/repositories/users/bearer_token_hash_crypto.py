"""SoAI - Bearer token hash encryption helpers [backend/database/repositories/users/bearer_token_hash_crypto.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.security.encryption import decrypt_data, encrypt_data

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

__all__ = ("BearerTokenHashCryptor",)


@dataclass(frozen=True, slots=True)
class BearerTokenHashCryptor:
    fernets: tuple[Fernet, ...]

    def ensure_crypto(self) -> None:
        if not self.fernets:
            raise StateError("Encryption keys are not available.")

    def encrypt_hash(self, value: str) -> str:
        self.ensure_crypto()
        if not value:
            raise StateError("Bearer token hash must not be empty.")
        encrypted = encrypt_data(self.fernets, value)
        if not encrypted:
            raise StateError("Failed to encrypt bearer token hash.")
        return encrypted

    def decrypt_hash(self, value: str | None) -> str | None:
        if not value:
            return None
        self.ensure_crypto()
        decrypted = decrypt_data(self.fernets, value)
        if not decrypted:
            raise StateError("Failed to decrypt bearer token hash.")
        return decrypted
