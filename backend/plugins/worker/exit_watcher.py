"""SoAI - Parent-side plugin worker exit monitoring [backend/plugins/worker/exit_watcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

from core.concurrency.cancellation_cleanup import cancellation_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.concurrency.task_finalization import cancel_and_await_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError
from core.logging.trace import get_logger
from core.runtime.backend_process_tracking import cleanup_backend_process_identities
from core.timing.constants import SETUP_TIMEOUT_SEC, STANDARD_DELAY_SEC
from plugins.package_leases import remove_plugin_package_lease
from plugins.worker.controller_faults import mark_worker_crashed
from plugins.worker.descendant_ownership import (
    WorkerDescendantRequest,
    capture_worker_descendants_batch,
)
from plugins.worker.runtime_failure_reporting import schedule_runtime_recovery

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.ipc.multiplexed import MultiplexedIpcServer
    from core.runtime.backend_process_tracking import BackendProcessIdentity
    from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol
    from plugins.worker.runtime_registry import PluginWorkerRuntime, PluginWorkerRuntimeRegistry

__all__ = ("PluginWorkerExitWatcher",)

LOGGER_NAME = "SoAI.plugins.worker.exit_watcher"
OPERATION_CAPTURE_DESCENDANTS = "plugins.worker.exit_watcher.capture_descendants"
OPERATION_OWNERSHIP_FAILED = "plugins.worker.ownership_failed"
OPERATION_REMOVE_PACKAGE_LEASE = "plugins.worker.exit_watcher.remove_package_lease"


@dataclass(slots=True, eq=False)
class _WorkerObservationProcess:
    request: WorkerDescendantRequest
    failure: asyncio.Future[psutil.Error | OSError]
    pending_batch: asyncio.Task[None] | None = None


@dataclass(frozen=True, slots=True)
class _RetainedDescendantCleanup:
    plugin_name: str
    identities: list[BackendProcessIdentity]


class PluginWorkerExitWatcher:
    def __init__(
        self,
        *,
        manager: PluginManagerRuntimeProtocol,
        registry: PluginWorkerRuntimeRegistry,
        server: MultiplexedIpcServer,
        release_worker_reservations: Callable[[int], None],
    ) -> None:
        self._manager = manager
        self._registry = registry
        self._server = server
        self._release_worker_reservations = release_worker_reservations
        self._worker_monitors: dict[int, asyncio.Task[None]] = {}
        self._observed: dict[int, _WorkerObservationProcess] = {}
        self._observer: asyncio.Task[None] | None = None
        self._retained_cleanups: dict[int, _RetainedDescendantCleanup] = {}

    def watch(self, *, plugin_name: str, runtime: PluginWorkerRuntime) -> None:
        worker_id = int(runtime.worker_id)
        self._worker_monitors[worker_id] = create_ephemeral_task(
            self._monitor_worker_exit(plugin_name=plugin_name, runtime=runtime),
            name=f"plugin-worker-monitor-{plugin_name}",
        )

    async def cancel(self, worker_id: int) -> None:
        worker_id = int(worker_id)
        task = self._worker_monitors.get(worker_id)
        retained = self._retained_cleanups.get(worker_id)
        if task is not None and task.done() and retained is not None:
            await self._release_descendants(
                worker_id,
                retained,
                failure_message="Exited plugin worker resources could not be released.",
            )
        else:
            await cancel_and_await_task(task)
        if self._worker_monitors.get(worker_id) is task:
            self._worker_monitors.pop(worker_id, None)

    async def cancel_all(self) -> None:
        cancellations = [self.cancel(worker_id) for worker_id in tuple(self._worker_monitors)]
        results = await asyncio.gather(*cancellations, return_exceptions=True)
        observer, self._observer = self._observer, None
        await cancel_and_await_task(observer)
        for result in results:
            if isinstance(result, BaseException):
                raise result

    async def _monitor_worker_exit(
        self,
        *,
        plugin_name: str,
        runtime: PluginWorkerRuntime,
    ) -> None:
        process = runtime.worker.process
        if process is None:
            return
        worker_id = int(runtime.worker_id)
        observed = _WorkerObservationProcess(
            WorkerDescendantRequest(process.pid, None, ()),
            asyncio.get_running_loop().create_future(),
        )
        self._observed[worker_id] = observed
        self._ensure_descendant_observer()
        identities: list[BackendProcessIdentity] = []
        cleanup_attempted = False
        exit_wait = create_ephemeral_task(
            process.wait(),
            name=f"plugin-worker-exit-wait-{plugin_name}",
        )
        try:
            while process.returncode is None:
                waiters: set[asyncio.Future[int] | asyncio.Future[psutil.Error | OSError]] = {
                    exit_wait,
                    observed.failure,
                }
                await asyncio.wait(
                    waiters, timeout=STANDARD_DELAY_SEC, return_when=asyncio.FIRST_COMPLETED
                )
                if process.returncode is None and observed.failure.done():
                    log_exception(
                        get_logger(LOGGER_NAME),
                        observed.failure.result(),
                        message="Plugin worker descendant ownership could not be observed.",
                        operation=OPERATION_CAPTURE_DESCENDANTS,
                        details={"plugin_name": plugin_name},
                    )
                    await runtime.worker.terminate(operation=OPERATION_OWNERSHIP_FAILED)
                    break
            identities = await self._release_observation(worker_id, observed)
            async with self._manager.dependencies.infrastructure.lifecycle.plugin_lock_scope(
                plugin_name,
            ):
                returncode = process.returncode
                if returncode is None:
                    raise ProcessError("Plugin worker termination could not be confirmed.")
                cleanup_attempted = True
                try:
                    await self._release_descendants(
                        worker_id,
                        _RetainedDescendantCleanup(plugin_name, identities),
                        failure_message="Exited plugin worker resources could not be released.",
                    )
                except ProcessError:
                    await self._report_worker_crash(
                        plugin_name=plugin_name, runtime=runtime, returncode=returncode
                    )
                    raise
                await self._reconcile_worker_exit(
                    plugin_name=plugin_name, runtime=runtime, returncode=returncode
                )
        finally:
            try:
                await cancel_and_await((exit_wait,), task_label="plugin worker exit wait")
            finally:
                identities = await self._release_observation(worker_id, observed)
                if process.returncode is not None and not cleanup_attempted:
                    await self._release_descendants(
                        worker_id,
                        _RetainedDescendantCleanup(plugin_name, identities),
                        failure_message="Stopped plugin worker resources could not be released.",
                    )
        self._worker_monitors.pop(runtime.worker_id, None)

    def _ensure_descendant_observer(self) -> None:
        if self._observed and (self._observer is None or self._observer.done()):
            self._observer = create_ephemeral_task(
                self._observe_descendants(), name="plugin-worker-descendant-observer"
            )

    async def _observe_descendants(self) -> None:
        while self._observed:
            observed = tuple(self._observed.values())
            batch = create_ephemeral_task(
                self._capture_descendants(observed), name="plugin-worker-descendant-census"
            )
            for entry in observed:
                entry.pending_batch = batch
            await batch
            await asyncio.sleep(STANDARD_DELAY_SEC)

    @staticmethod
    async def _capture_descendants(observed: tuple[_WorkerObservationProcess, ...]) -> None:
        captures = await run_joined_thread_call(
            capture_worker_descendants_batch,
            [entry.request for entry in observed],
            task_name=OPERATION_CAPTURE_DESCENDANTS,
        )
        for entry, capture in zip(observed, captures, strict=True):
            entry.request = WorkerDescendantRequest(
                entry.request.worker_pid, capture.expected_create_time_ms, capture.identities
            )
            if capture.failure is not None and not entry.failure.done():
                entry.failure.set_result(capture.failure)

    async def _release_observation(
        self, worker_id: int, observed: _WorkerObservationProcess
    ) -> list[BackendProcessIdentity]:
        batch = observed.pending_batch
        if batch is not None and not batch.done():
            await asyncio.wait_for(asyncio.shield(batch), timeout=SETUP_TIMEOUT_SEC)
        if self._observed.get(worker_id) is observed:
            self._observed.pop(worker_id)
        observer = self._observer
        if not self._observed and observer is not None:
            await cancel_and_await_task(observer)
            if self._observer is observer:
                self._observer = None
            self._ensure_descendant_observer()
        return list(observed.request.retained)

    async def _release_descendants(
        self,
        worker_id: int,
        cleanup: _RetainedDescendantCleanup,
        *,
        failure_message: str,
    ) -> None:
        result = await cancellation_cleanup(
            cleanup_backend_process_identities(
                cleanup.identities, plugin_name=cleanup.plugin_name, logger=get_logger(LOGGER_NAME)
            )
        )
        if result.succeeded:
            self._retained_cleanups.pop(worker_id, None)
            return
        self._retained_cleanups[worker_id] = _RetainedDescendantCleanup(
            cleanup.plugin_name, list(result.failed)
        )
        raise ProcessError(failure_message)

    async def _reconcile_worker_exit(
        self,
        *,
        plugin_name: str,
        runtime: PluginWorkerRuntime,
        returncode: int,
    ) -> None:
        self._release_worker_reservations(runtime.worker_id)
        try:
            remove_plugin_package_lease(runtime.package_lease_path)
        except OSError as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Exited plugin worker package lease could not be removed.",
                operation=OPERATION_REMOVE_PACKAGE_LEASE,
                details={"plugin_name": plugin_name, "worker_id": runtime.worker_id},
                level="error",
            )
        await self._server.forget_worker_secret(runtime.worker_id)
        shutting_down = self._manager.dependencies.infrastructure.lifecycle.shutdown_event.is_set()
        if await self._registry.should_ignore_worker_exit(
            plugin_name=plugin_name,
            runtime=runtime,
            shutting_down=shutting_down,
        ):
            return
        if not await self._registry.pop_loaded_runtime_if_current(
            plugin_name=plugin_name,
            runtime=runtime,
        ):
            return
        async with self._manager.state.locks.load_lock:
            current_instance = self._manager.state.catalog.loaded_plugin_instances.get(plugin_name)
            if current_instance is not None and current_instance is not runtime.proxy:
                return
            self._manager.state.catalog.loaded_plugin_instances.pop(plugin_name, None)
            self._manager.state.catalog.loaded_plugin_surfaces.pop(plugin_name, None)
        await self._report_worker_crash(
            plugin_name=plugin_name, runtime=runtime, returncode=returncode
        )

    async def _report_worker_crash(
        self,
        *,
        plugin_name: str,
        runtime: PluginWorkerRuntime,
        returncode: int,
    ) -> None:
        transitioned = await mark_worker_crashed(
            self._manager,
            plugin_name=plugin_name,
            returncode=returncode,
            expected_instance=runtime.proxy,
        )
        if transitioned:
            schedule_runtime_recovery(
                self._manager,
                plugin_name=plugin_name,
                reason="Plugin worker exited unexpectedly; recovering its runtime.",
            )
