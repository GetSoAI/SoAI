"""SoAI - Argon2 password hashing and verification context [backend/core/security/password_hashing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from core.errors.exceptions import StateError, ValidationError

__all__ = ("PasswordContext",)


class PasswordContext:
    def __init__(self) -> None:
        self._argon2 = PasswordHasher()

    def hash(self, password: str) -> str:
        if not isinstance(password, str) or not password:
            raise ValidationError("Password must be a non-empty string.")
        return self._argon2.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        normalized_hash = password_hash.strip()
        if not normalized_hash:
            raise StateError("Stored password hash is empty.")
        if normalized_hash.startswith("$argon2"):
            return self._verify_argon2(password, normalized_hash)
        raise StateError("Stored password hash uses an unsupported scheme.")

    def _verify_argon2(self, password: str, normalized_hash: str) -> bool:
        try:
            return bool(self._argon2.verify(normalized_hash, password))
        except VerifyMismatchError:
            return False
        except InvalidHashError as exception:
            raise StateError("Stored Argon2 password hash is malformed.") from exception
        except VerificationError as exception:
            raise StateError("Argon2 password verification failed.") from exception
