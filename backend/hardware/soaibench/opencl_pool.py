"""SoAI - SoAIBench owned OpenCL child admission [backend/hardware/soaibench/opencl_pool.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import (
    create_bounded_thread_pool,
    shutdown_bounded_pool_executor,
)
from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_then_cleanup,
)
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from hardware.soaibench.opencl_child import (
    SoAIBenchOpenCLChild,
    spawn_soaibench_opencl_child,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("SoAIBenchAdmissionCleanupError", "SoAIBenchOpenCLPool")

OPENCL_POOL_MAX_IN_FLIGHT = 2


class SoAIBenchAdmissionCleanupError(Exception):
    child: SoAIBenchOpenCLChild
    cleanup_failure: BaseException

    def __init__(
        self,
        child: SoAIBenchOpenCLChild,
        cleanup_failure: BaseException,
    ) -> None:
        super().__init__(child, cleanup_failure)
        self.child = child
        self.cleanup_failure = cleanup_failure


class SoAIBenchOpenCLPool:
    def __init__(self, logger: LoggerProtocol) -> None:
        self._logger = logger
        self._condition = asyncio.Condition()
        self._active_leases = 0
        self._children: set[SoAIBenchOpenCLChild] = set()
        self._closed = False
        self._numerical_validation_pool = create_bounded_thread_pool(
            label="soaibench-numerical-validation",
            thread_name_prefix="soaibench-numerical",
            max_workers=2,
            max_in_flight=2,
        )

    @asynccontextmanager
    async def lease(
        self,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[SoAIBenchOpenCLChild]:
        child = await self._acquire(stop_event)
        try:
            yield child
        finally:
            await self._release(child)

    async def shutdown(self) -> None:
        async with self._condition:
            self._closed = True
            self._condition.notify_all()
            children = tuple(self._children)
        first_failure: BaseException | None = None
        for child in children:
            try:
                await uncancel_then_cleanup(child.close())
            except asyncio.CancelledError as exception:
                if first_failure is None:
                    first_failure = exception
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                if first_failure is None:
                    first_failure = exception
        try:
            if first_failure is not None:
                raise first_failure
            self._logger.debug("SoAIBench OpenCL child admission has been shut down.")
        finally:
            shutdown_bounded_pool_executor(self._numerical_validation_pool)

    async def notify_waiters(self) -> None:
        async with self._condition:
            self._condition.notify_all()

    async def _acquire(self, stop_event: asyncio.Event | None) -> SoAIBenchOpenCLChild:
        async with self._condition:
            while self._active_leases >= OPENCL_POOL_MAX_IN_FLIGHT and not self._closed:
                if stop_event is not None and stop_event.is_set():
                    raise asyncio.CancelledError()
                await self._condition.wait()
            if self._closed:
                raise ValidationError("SoAIBench OpenCL child admission is shut down.")
            if stop_event is not None and stop_event.is_set():
                raise asyncio.CancelledError()
            self._active_leases += 1
            try:
                child = await uncancel_then_cleanup(
                    spawn_soaibench_opencl_child(
                        self._logger,
                        self._numerical_validation_pool,
                    ),
                )
            except asyncio.CancelledError:
                self._active_leases -= 1
                self._condition.notify_all()
                raise
            except HANDLED_RUNTIME_EXCEPTIONS:
                self._active_leases -= 1
                self._condition.notify_all()
                raise
            self._children.add(child)
        if current_task_has_pending_cancellation():
            try:
                await self._release(child)
            except asyncio.CancelledError as exception:
                raise SoAIBenchAdmissionCleanupError(child, exception) from exception
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                raise SoAIBenchAdmissionCleanupError(child, exception) from exception
            raise asyncio.CancelledError()
        self._logger.debug("SoAIBench OpenCL child process started.")
        return child

    async def _release(self, child: SoAIBenchOpenCLChild) -> None:
        await uncancel_then_cleanup(self._close_and_update_admission(child))

    async def _close_and_update_admission(self, child: SoAIBenchOpenCLChild) -> None:
        released = False
        try:
            await child.close()
            released = True
        finally:
            async with self._condition:
                if released:
                    self._children.discard(child)
                    if self._active_leases <= 0:
                        raise ValidationError("SoAIBench OpenCL child lease state is invalid.")
                    self._active_leases -= 1
                self._condition.notify_all()
