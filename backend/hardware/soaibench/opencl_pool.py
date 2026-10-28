"""SoAI - SoAIBench owned OpenCL child admission [backend/hardware/soaibench/opencl_pool.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    shutdown_bounded_pool_executor,
)
from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_then_cleanup,
)
from core.di.validation import require_dependencies
from core.errors.exceptions import ProcessError, ProcessGroupCleanupError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.ipc.multiplexed import MultiplexedIpcServer
from core.system.async_process_spawning import retain_managed_process_cleanup
from hardware.soaibench.opencl_child import SoAIBenchOpenCLChild
from hardware.soaibench.opencl_child_startup import spawn_soaibench_opencl_child

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "OPENCL_POOL_MAX_IN_FLIGHT",
    "SoAIBenchAdmissionCleanupError",
    "SoAIBenchOpenCLPool",
    "SoAIBenchOpenCLPoolDependencies",
)

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


@dataclass(frozen=True, slots=True)
class SoAIBenchOpenCLPoolDependencies:
    logger: LoggerProtocol
    server: MultiplexedIpcServer
    numerical_validation_pool: BoundedBlockingPool
    cleanup_pool: BoundedBlockingPool

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SoAIBenchOpenCLPoolDependencies",
            logger=self.logger,
            server=self.server,
            numerical_validation_pool=self.numerical_validation_pool,
            cleanup_pool=self.cleanup_pool,
        )


class SoAIBenchOpenCLPool:
    def __init__(self, deps: SoAIBenchOpenCLPoolDependencies) -> None:
        self._logger = deps.logger
        self._server = deps.server
        self._next_worker_id = 0
        self._condition = asyncio.Condition()
        self._active_leases = 0
        self._reservations = 0
        self._children: set[SoAIBenchOpenCLChild] = set()
        self._retained: set[SoAIBenchOpenCLChild] = set()
        self._verified_exit_releases: dict[SoAIBenchOpenCLChild, Callable[[], Awaitable[bool]]] = {}
        self._closed = False
        self._numerical_validation_pool = deps.numerical_validation_pool
        self._cleanup_pool = deps.cleanup_pool

    @asynccontextmanager
    async def lease(
        self,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[SoAIBenchOpenCLChild]:
        child = await self._acquire(stop_event)
        try:
            yield child
        finally:
            primary_exception = sys.exception()
            if primary_exception is None:
                await self._release(child)
            else:
                try:
                    await self._release(child)
                except asyncio.CancelledError as cleanup_exception:
                    primary_exception.add_note(
                        f"SoAI Bench OpenCL child release also failed: {cleanup_exception}"
                    )
                except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
                    primary_exception.add_note(
                        f"SoAI Bench OpenCL child release also failed: {cleanup_exception}"
                    )

    async def shutdown(self) -> None:
        async with self._condition:
            self._closed = True
            self._condition.notify_all()
        await uncancel_then_cleanup(self._settled_children())
        children = tuple(self._children)
        first_failure: BaseException | None = None
        for child in children:
            try:
                await uncancel_then_cleanup(child.close())
            except asyncio.CancelledError as exception:
                if first_failure is None:
                    first_failure = exception
            except ProcessError as exception:
                if not child.exit_verified and first_failure is None:
                    first_failure = exception
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                if first_failure is None:
                    first_failure = exception
        try:
            if first_failure is not None:
                raise first_failure
            self._logger.debug("SoAI Bench OpenCL child admission has been shut down.")
        finally:
            try:
                await self._server.shutdown()
            finally:
                shutdown_bounded_pool_executor(self._numerical_validation_pool)
                shutdown_bounded_pool_executor(self._cleanup_pool)

    async def notify_waiters(self) -> None:
        async with self._condition:
            self._condition.notify_all()

    async def release_after_verified_exit(
        self,
        child: SoAIBenchOpenCLChild,
        release: Callable[[], Awaitable[bool]],
    ) -> None:
        async with self._condition:
            if child in self._retained:
                self._verified_exit_releases[child] = release
                return
        await release()

    async def reconcile_retained(self) -> None:
        async with self._condition:
            retained = () if self._closed else tuple(self._retained)
        for child in retained:
            try:
                await self._release(child)
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                self._logger.debug(
                    "Retained SoAI Bench OpenCL child reconciliation did not complete: %s",
                    type(exception).__name__,
                )
                continue
            release = self._verified_exit_releases.pop(child, None)
            if release is not None:
                await uncancel_then_cleanup(release())

    async def _acquire(self, stop_event: asyncio.Event | None) -> SoAIBenchOpenCLChild:
        await self.reconcile_retained()
        async with self._condition:
            while self._active_leases >= OPENCL_POOL_MAX_IN_FLIGHT and not self._closed:
                if stop_event is not None and stop_event.is_set():
                    raise asyncio.CancelledError()
                await self._condition.wait()
            if self._closed:
                raise ValidationError("SoAI Bench OpenCL child admission is shut down.")
            if stop_event is not None and stop_event.is_set():
                raise asyncio.CancelledError()
            self._active_leases += 1
            self._reservations += 1
            self._next_worker_id += 1
            worker_id = self._next_worker_id
        try:
            child = await uncancel_then_cleanup(
                spawn_soaibench_opencl_child(
                    self._logger,
                    self._numerical_validation_pool,
                    self._server,
                    worker_id,
                    cleanup_pool=self._cleanup_pool,
                ),
            )
        except ProcessGroupCleanupError as exception:
            retained_child = SoAIBenchOpenCLChild(
                retain_managed_process_cleanup(exception),
                self._logger,
                self._numerical_validation_pool,
                self._server,
                worker_id,
                (),
                cleanup_pool=self._cleanup_pool,
            )
            await uncancel_then_cleanup(self._register(retained_child, retained=True))
            raise SoAIBenchAdmissionCleanupError(retained_child, exception) from exception
        except asyncio.CancelledError:
            await uncancel_then_cleanup(self._cancel_reservation())
            raise
        except HANDLED_RUNTIME_EXCEPTIONS:
            await uncancel_then_cleanup(self._cancel_reservation())
            raise
        admitted = await uncancel_then_cleanup(self._register(child, retained=False))
        if not admitted or current_task_has_pending_cancellation():
            try:
                await self._release(child)
            except asyncio.CancelledError as exception:
                raise SoAIBenchAdmissionCleanupError(child, exception) from exception
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                raise SoAIBenchAdmissionCleanupError(child, exception) from exception
            if not admitted:
                raise ValidationError("SoAI Bench OpenCL child admission is shut down.")
            raise asyncio.CancelledError()
        self._logger.debug("SoAI Bench OpenCL child process started.")
        return child

    async def _register(self, child: SoAIBenchOpenCLChild, *, retained: bool) -> bool:
        async with self._condition:
            self._reservations -= 1
            self._children.add(child)
            if retained:
                self._retained.add(child)
            self._condition.notify_all()
            return not self._closed

    async def _cancel_reservation(self) -> None:
        async with self._condition:
            self._reservations -= 1
            self._active_leases -= 1
            self._condition.notify_all()

    async def _settled_children(self) -> None:
        async with self._condition:
            await self._condition.wait_for(lambda: self._reservations == 0)

    async def _release(self, child: SoAIBenchOpenCLChild) -> None:
        await uncancel_then_cleanup(self._close_and_update_admission(child))

    async def _close_and_update_admission(self, child: SoAIBenchOpenCLChild) -> None:
        try:
            await child.close()
            if not child.exit_verified:
                raise ProcessError("SoAI Bench OpenCL child exit could not be verified.")
        finally:
            async with self._condition:
                if not child.exit_verified:
                    self._retained.add(child)
                elif child in self._children:
                    self._children.discard(child)
                    self._retained.discard(child)
                    if self._active_leases <= 0:
                        raise ValidationError("SoAI Bench OpenCL child lease state is invalid.")
                    self._active_leases -= 1
                self._condition.notify_all()
