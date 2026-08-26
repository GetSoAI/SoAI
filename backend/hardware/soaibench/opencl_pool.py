"""SoAI - SoAIBench lazy OpenCL process-pool lifecycle [backend/hardware/soaibench/opencl_pool.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("SoAIBenchOpenCLPool",)

OPENCL_POOL_MAX_WORKERS = 2
OPENCL_POOL_MAX_IN_FLIGHT = 2


class SoAIBenchOpenCLPool:
    def __init__(
        self,
        logger: LoggerProtocol,
        pool_factory: Callable[[], BoundedBlockingPool],
    ) -> None:
        self._logger = logger
        self._pool_factory = pool_factory
        self._condition = asyncio.Condition()
        self._pool: BoundedBlockingPool | None = None
        self._active_leases = 0
        self._closed = False

    @asynccontextmanager
    async def lease(self) -> AsyncGenerator[BoundedBlockingPool]:
        pool = await self._acquire()
        try:
            yield pool
        finally:
            await self._release()

    async def shutdown(self) -> None:
        async with self._condition:
            self._closed = True
            while self._active_leases > 0:
                await self._condition.wait()
            pool = self._pool
            self._pool = None
        if pool is None:
            return
        pool.executor.shutdown(wait=False, cancel_futures=True)
        self._logger.debug("SoAIBench OpenCL process pool has been shut down.")

    async def _acquire(self) -> BoundedBlockingPool:
        async with self._condition:
            if self._closed:
                raise ValidationError("SoAIBench OpenCL pool is shut down.")
            if self._pool is None:
                self._pool = self._pool_factory()
                self._logger.debug("SoAIBench OpenCL process pool created.")
            self._active_leases += 1
            return self._pool

    async def _release(self) -> None:
        async with self._condition:
            if self._active_leases <= 0:
                raise ValidationError("SoAIBench OpenCL pool lease state is invalid.")
            self._active_leases -= 1
            if self._active_leases == 0:
                self._condition.notify_all()
