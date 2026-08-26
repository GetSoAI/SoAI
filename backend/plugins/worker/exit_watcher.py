"""SoAI - Parent-side plugin worker exit monitoring [backend/plugins/worker/exit_watcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_logging import log_exception
from core.ipc.multiplexed import MultiplexedIpcServer
from core.logging.trace import get_logger
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC
from plugins.package_leases import remove_plugin_package_lease
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.worker.controller_faults import mark_worker_crashed
from plugins.worker.runtime_registry import (
    PluginWorkerRuntime,
    PluginWorkerRuntimeRegistry,
)

__all__ = ("PluginWorkerExitWatcher",)

LOGGER_NAME = "SoAI.plugins.worker.exit_watcher"
OPERATION_REMOVE_PACKAGE_LEASE = "plugins.worker.exit_watcher.remove_package_lease"


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

    def watch(self, *, plugin_name: str, runtime: PluginWorkerRuntime) -> None:
        worker_id = int(runtime.worker_id)
        self._worker_monitors[worker_id] = create_ephemeral_task(
            self._monitor_worker_exit(plugin_name=plugin_name, runtime=runtime),
            name=f"plugin-worker-monitor-{plugin_name}",
        )

    async def cancel(self, worker_id: int) -> None:
        task = self._worker_monitors.pop(int(worker_id), None)
        await cancel_and_await((task,), task_label="plugin worker monitor")

    async def cancel_all(self) -> None:
        tasks = tuple(self._worker_monitors.values())
        self._worker_monitors.clear()
        await cancel_and_await(tasks, task_label="plugin worker monitors")

    async def _monitor_worker_exit(
        self,
        *,
        plugin_name: str,
        runtime: PluginWorkerRuntime,
    ) -> None:
        process = runtime.worker.process
        if process is None:
            return
        returncode = await self._wait_for_worker_exit_without_deadline(process)
        async with self._manager.dependencies.infrastructure.lifecycle.plugin_lock_scope(
            plugin_name,
        ):
            self._worker_monitors.pop(runtime.worker_id, None)
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
            shutting_down = (
                self._manager.dependencies.infrastructure.lifecycle.shutdown_event.is_set()
            )
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
                self._manager.state.catalog.loaded_plugin_instances.pop(plugin_name, None)
                self._manager.state.catalog.loaded_plugin_surfaces.pop(plugin_name, None)
            await mark_worker_crashed(
                self._manager,
                plugin_name=plugin_name,
                returncode=returncode,
            )

    async def _wait_for_worker_exit_without_deadline(
        self,
        process: asyncio.subprocess.Process,
    ) -> int:
        while True:
            try:
                return await asyncio.wait_for(process.wait(), timeout=LONG_IDLE_TIMEOUT_SEC)
            except TimeoutError:
                continue
