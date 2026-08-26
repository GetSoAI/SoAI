"""SoAI - Authentication config container [backend/features/api/runtime/container/auth_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading

from core.errors.exceptions import StateError

__all__ = ("AuthConfig",)

_DEFAULT_JWT_ALGORITHM = "HS256"


class AuthConfig:
    __slots__ = (
        "_algorithm",
        "_lock",
        "_primary_signing_secret",
        "_verification_secrets",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._primary_signing_secret: str | None = None
        self._verification_secrets: tuple[str, ...] = ()
        self._algorithm: str = _DEFAULT_JWT_ALGORITHM

    def configure(
        self,
        *,
        primary_signing_secret: str,
        verification_secrets: tuple[str, ...],
        algorithm: str | None = None,
    ) -> None:
        if (
            not primary_signing_secret
            or not verification_secrets
            or verification_secrets[0] != primary_signing_secret
            or any(not secret for secret in verification_secrets)
        ):
            raise StateError("Authentication secret keyring is invalid.")
        with self._lock:
            self._primary_signing_secret = primary_signing_secret
            self._verification_secrets = verification_secrets
            if algorithm is not None:
                self._algorithm = algorithm

    @property
    def primary_signing_secret(self) -> str | None:
        with self._lock:
            return self._primary_signing_secret

    @property
    def verification_secrets(self) -> tuple[str, ...]:
        with self._lock:
            return self._verification_secrets

    @property
    def algorithm(self) -> str:
        with self._lock:
            return self._algorithm
