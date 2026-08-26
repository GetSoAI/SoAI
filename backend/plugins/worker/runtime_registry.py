"""SoAI - Plugin worker runtime bookkeeping [backend/plugins/worker/runtime_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.ipc.protocols import ManagedIpcWorkerProtocol
from plugins.worker.proxy import ProxyPluginInstance

__all__ = (
    "PluginWorkerRuntime",
    "PluginWorkerRuntimeRegistry",
    "PluginWorkerRuntimeRegistryDependencies",
)


@dataclass(slots=True)
class PluginWorkerRuntime:
    worker_id: int
    worker: ManagedIpcWorkerProtocol
    proxy: ProxyPluginInstance
    package_lease_path: str


@dataclass(frozen=True, slots=True)
class PluginWorkerRuntimeRegistryDependencies:
    runtime_lock: asyncio.Lock
    workers: dict[str, PluginWorkerRuntime]
    worker_id_to_plugin_name: dict[int, str]
    stopping_worker_ids: set[int]
    stopping_plugin_names: set[str]
    next_worker_id: int

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginWorkerRuntimeRegistryDependencies",
            runtime_lock=self.runtime_lock,
            workers=self.workers,
            worker_id_to_plugin_name=self.worker_id_to_plugin_name,
            stopping_worker_ids=self.stopping_worker_ids,
            stopping_plugin_names=self.stopping_plugin_names,
            next_worker_id=self.next_worker_id,
        )


class PluginWorkerRuntimeRegistry:
    def __init__(self, deps: PluginWorkerRuntimeRegistryDependencies) -> None:
        self._workers = deps.workers
        self._worker_id_to_plugin_name = deps.worker_id_to_plugin_name
        self._stopping_worker_ids = deps.stopping_worker_ids
        self._stopping_plugin_names = deps.stopping_plugin_names
        self._runtime_lock = deps.runtime_lock
        self._next_worker_id = deps.next_worker_id

    async def allocate_worker_id(self, *, plugin_name: str) -> int:
        async with self._runtime_lock:
            worker_id = self._next_worker_id
            self._next_worker_id += 1
            self._worker_id_to_plugin_name[worker_id] = plugin_name
            return worker_id

    async def discard_worker_id(self, worker_id: int) -> None:
        async with self._runtime_lock:
            self._worker_id_to_plugin_name.pop(int(worker_id), None)
            self._stopping_worker_ids.discard(int(worker_id))

    async def resolve_plugin_name_for_worker(self, worker_id: int) -> str | None:
        async with self._runtime_lock:
            return self._worker_id_to_plugin_name.get(int(worker_id))

    async def begin_stop(self, plugin_name: str) -> PluginWorkerRuntime | None:
        async with self._runtime_lock:
            self._stopping_plugin_names.add(plugin_name)
            runtime = self._workers.pop(plugin_name, None)
            if runtime is not None:
                self._stopping_worker_ids.add(runtime.worker_id)
            return runtime

    async def restore_after_stop_failure(
        self,
        *,
        plugin_name: str,
        runtime: PluginWorkerRuntime,
    ) -> None:
        async with self._runtime_lock:
            self._workers[plugin_name] = runtime
            self._stopping_worker_ids.discard(runtime.worker_id)
            self._stopping_plugin_names.discard(plugin_name)
            self._worker_id_to_plugin_name[runtime.worker_id] = plugin_name

    async def finalize_stop(self, plugin_name: str, runtime: PluginWorkerRuntime) -> bool:
        async with self._runtime_lock:
            self._worker_id_to_plugin_name.pop(runtime.worker_id, None)
            should_cancel_monitor = runtime.worker_id in self._stopping_worker_ids
            self._stopping_worker_ids.discard(runtime.worker_id)
            self._stopping_plugin_names.discard(plugin_name)
            return should_cancel_monitor

    async def cancel_stop_flag(self, plugin_name: str) -> None:
        async with self._runtime_lock:
            self._stopping_plugin_names.discard(plugin_name)

    async def register_loaded_runtime(
        self,
        *,
        plugin_name: str,
        runtime: PluginWorkerRuntime,
    ) -> None:
        async with self._runtime_lock:
            self._workers[plugin_name] = runtime

    async def pop_loaded_runtime_if_current(
        self,
        *,
        plugin_name: str,
        runtime: PluginWorkerRuntime,
    ) -> bool:
        async with self._runtime_lock:
            current_runtime = self._workers.get(plugin_name)
            if current_runtime is not runtime:
                return False
            self._workers.pop(plugin_name, None)
            self._worker_id_to_plugin_name.pop(runtime.worker_id, None)
            return True

    async def should_ignore_worker_exit(
        self,
        *,
        plugin_name: str,
        runtime: PluginWorkerRuntime,
        shutting_down: bool,
    ) -> bool:
        async with self._runtime_lock:
            if shutting_down:
                return True
            if runtime.worker_id in self._stopping_worker_ids:
                return True
            if plugin_name in self._stopping_plugin_names:
                return True
            return self._workers.get(plugin_name) is not runtime

    async def clear_all(self) -> None:
        async with self._runtime_lock:
            self._workers.clear()
            self._worker_id_to_plugin_name.clear()
            self._stopping_worker_ids.clear()
            self._stopping_plugin_names.clear()

    async def snapshot_runtimes_for_shutdown(self) -> list[PluginWorkerRuntime]:
        async with self._runtime_lock:
            runtimes = list(self._workers.values())
            for runtime in runtimes:
                self._stopping_worker_ids.add(runtime.worker_id)
            self._stopping_plugin_names.update(self._workers.keys())
            return runtimes

    async def snapshot_loaded_runtimes(self) -> list[PluginWorkerRuntime]:
        async with self._runtime_lock:
            return list(self._workers.values())
