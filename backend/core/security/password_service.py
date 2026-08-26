"""SoAI - Pooled asynchronous password hashing and verification service [backend/core/security/password_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    run_bounded_blocking_call,
)
from core.concurrency.singleflight import AsyncSingleflight, ResultCopyMode
from core.di.validation import require_dependencies
from core.security.password_hashing import PasswordContext

__all__ = (
    "PasswordService",
    "PasswordServiceDependencies",
)

_TIMING_SAFE_SENTINEL: str = "timing_safe_sentinel"
_TIMING_SAFE_SENTINEL_FLIGHT_KEY: str = "timing-safe-sentinel"


@dataclass(frozen=True, slots=True)
class PasswordServiceDependencies:
    pool: BoundedBlockingPool
    password_context: PasswordContext

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PasswordServiceDependencies",
            password_context=self.password_context,
            pool=self.pool,
        )


class PasswordService:
    def __init__(self, deps: PasswordServiceDependencies) -> None:
        self._pool = deps.pool
        self._password_context = deps.password_context
        self._timing_safe_sentinel_hash: str | None = None
        self._timing_safe_sentinel_singleflight: AsyncSingleflight[str, str] = AsyncSingleflight(
            ResultCopyMode.NONE
        )

    async def hash_password(self, password: str, *, timeout_sec: float | None = None) -> str:
        return await run_bounded_blocking_call(
            self._pool,
            self._password_context.hash,
            password,
            timeout_sec=timeout_sec,
        )

    async def verify_password(
        self,
        password: str,
        password_hash: str,
        *,
        timeout_sec: float | None = None,
    ) -> bool:
        return await run_bounded_blocking_call(
            self._pool,
            self._password_context.verify,
            password,
            password_hash,
            timeout_sec=timeout_sec,
        )

    async def timing_safe_sentinel_hash(self) -> str:
        cached_hash = self._timing_safe_sentinel_hash
        if cached_hash is not None:
            return cached_hash
        return await self._timing_safe_sentinel_singleflight.execute_or_wait(
            _TIMING_SAFE_SENTINEL_FLIGHT_KEY,
            self._generate_timing_safe_sentinel_hash,
        )

    async def _generate_timing_safe_sentinel_hash(self) -> str:
        password_hash = await self.hash_password(_TIMING_SAFE_SENTINEL)
        self._timing_safe_sentinel_hash = password_hash
        return password_hash
