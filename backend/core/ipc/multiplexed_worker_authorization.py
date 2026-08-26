"""SoAI - Multiplexed IPC worker authorization state [backend/core/ipc/multiplexed_worker_authorization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exceptions import ValidationError

__all__ = ("MultiplexedWorkerAuthorization",)


class MultiplexedWorkerAuthorization:
    def __init__(self) -> None:
        self._expected_worker_secrets: dict[int, str] = {}
        self._lock = asyncio.Lock()

    async def clear(self) -> None:
        async with self._lock:
            self._expected_worker_secrets.clear()

    async def expect_worker_secret(self, worker_id: int, *, worker_secret: str) -> None:
        normalized_secret = str(worker_secret or "").strip()
        if not normalized_secret:
            raise ValidationError("IPC worker_secret is required.")
        async with self._lock:
            self._expected_worker_secrets[int(worker_id)] = normalized_secret

    async def forget_worker_secret(self, worker_id: int) -> None:
        async with self._lock:
            self._expected_worker_secrets.pop(int(worker_id), None)

    async def require_worker_secret(self, worker_id: int, worker_secret: str | None) -> None:
        async with self._lock:
            expected_secret = self._expected_worker_secrets.get(int(worker_id))
        if expected_secret is None:
            return
        if worker_secret != expected_secret:
            raise ValidationError("IPC worker_secret mismatch.")
