"""SoAI - Core security service protocols [backend/core/security/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("PasswordServiceProtocol",)


class PasswordServiceProtocol(Protocol):
    async def hash_password(self, password: str, *, timeout_sec: float | None = None) -> str: ...

    async def verify_password(
        self,
        password: str,
        password_hash: str,
        *,
        timeout_sec: float | None = None,
    ) -> bool: ...

    async def timing_safe_sentinel_hash(self) -> str: ...
