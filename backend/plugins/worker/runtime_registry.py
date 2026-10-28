"""SoAI - Plugin worker runtime bookkeeping [backend/plugins/worker/runtime_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass

from core.concurrency.context import create_system_cancellation_id
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.ipc.protocols import ManagedIpcWorkerProtocol
from core.logging.trace import get_logger
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskFinalizerTrackerProtocol
from core.types.json import JSONDict
from plugins.worker.load_result import PluginWorkerLoadResult
from plugins.worker.proxy import ProxyPluginInstance

__all__ = (
    "PluginWorkerRuntime",
    "PluginWorkerRuntimeRegistry",
    "PluginWorkerRuntimeRegistryDependencies",
)


LOGGER_NAME = "SoAI.plugins.worker.runtime_registry"


@dataclass(slots=True)
class PluginWorkerRuntime:
    worker_id: int
    worker: ManagedIpcWorkerProtocol
    proxy: ProxyPluginInstance
    package_lease_path: str


@dataclass(slots=True)
class PluginWorkerAcquisition:
    worker_id: int
    worker: ManagedIpcWorkerProtocol
    package_lease_path: str | None = None
    acquisition_task: asyncio.Task[PluginWorkerLoadResult] | None = None


@dataclass(slots=True)
class PluginWorkerResourceOwnership:
    plugin_name: str
    resource: PluginWorkerRuntime | PluginWorkerAcquisition
    stop_task: asyncio.Task[None] | None = None
    cleanup_stage: str | None = None


@dataclass(frozen=True, slots=True)
class PluginWorkerRuntimeRegistryDependencies:
    runtime_lock: asyncio.Lock
    workers: dict[str, PluginWorkerRuntime]
    worker_id_to_plugin_name: dict[int, str]
    pending_worker_resources: dict[int, PluginWorkerResourceOwnership]
    next_worker_id: int

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginWorkerRuntimeRegistryDependencies",
            runtime_lock=self.runtime_lock,
            workers=self.workers,
            worker_id_to_plugin_name=self.worker_id_to_plugin_name,
            pending_worker_resources=self.pending_worker_resources,
            next_worker_id=self.next_worker_id,
        )


class PluginWorkerRuntimeRegistry:
    def __init__(self, deps: PluginWorkerRuntimeRegistryDependencies) -> None:
        self._workers = deps.workers
        self._worker_id_to_plugin_name = deps.worker_id_to_plugin_name
        self._pending_worker_resources = deps.pending_worker_resources
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
            self._pending_worker_resources.pop(int(worker_id), None)

    async def resolve_plugin_name_for_worker(self, worker_id: int) -> str | None:
        async with self._runtime_lock:
            return self._worker_id_to_plugin_name.get(int(worker_id))

    async def begin_acquisition(
        self,
        *,
        plugin_name: str,
        acquisition: PluginWorkerAcquisition,
        operation: Callable[[], Coroutine[None, None, PluginWorkerLoadResult]],
        finalizer_tracker: TaskFinalizerTrackerProtocol,
        cancellation_binder: TaskCancellationBinderProtocol,
    ) -> asyncio.Task[PluginWorkerLoadResult]:
        async with self._runtime_lock:
            self._pending_worker_resources[acquisition.worker_id] = PluginWorkerResourceOwnership(
                plugin_name, acquisition
            )
            task = spawn_tracked_task(
                operation(),
                name=f"plugin-worker-acquire-{acquisition.worker_id}",
                finalizer_tracker=finalizer_tracker,
                cancellation_binder=cancellation_binder,
                cancellation_id=create_system_cancellation_id("plugin_worker.acquire"),
                owner="plugin_worker.acquire",
                owner_observes_result=True,
            )
            acquisition.acquisition_task = task
            return task

    async def begin_stop(
        self,
        plugin_name: str,
        *,
        stop_operation: Callable[
            [str, PluginWorkerRuntime | PluginWorkerAcquisition], Coroutine[None, None, None]
        ],
        finalizer_tracker: TaskFinalizerTrackerProtocol,
        cancellation_binder: TaskCancellationBinderProtocol,
        expected_instance: PluginInstanceProtocol | None = None,
        expected_worker_id: int | None = None,
    ) -> list[asyncio.Task[None]]:
        async with self._runtime_lock:
            resources = {
                ownership.resource.worker_id: ownership.resource
                for ownership in self._pending_worker_resources.values()
                if ownership.plugin_name == plugin_name
            }
            current_runtime = self._workers.get(plugin_name)
            if current_runtime is not None:
                resources[current_runtime.worker_id] = current_runtime
            tasks: list[asyncio.Task[None]] = []
            for resource in resources.values():
                if expected_worker_id is not None and resource.worker_id != expected_worker_id:
                    continue
                if expected_instance is not None and (
                    not isinstance(resource, PluginWorkerRuntime)
                    or resource.proxy is not expected_instance
                ):
                    continue
                if self._workers.get(plugin_name) is resource:
                    self._workers.pop(plugin_name)
                if resource.worker_id not in self._pending_worker_resources:
                    self._pending_worker_resources[resource.worker_id] = (
                        PluginWorkerResourceOwnership(plugin_name, resource)
                    )
                ownership = self._pending_worker_resources[resource.worker_id]
                task = ownership.stop_task
                if task is None or task.done():
                    task = spawn_tracked_task(
                        stop_operation(plugin_name, resource),
                        name=f"plugin-worker-stop-{resource.worker_id}",
                        logger=get_logger(LOGGER_NAME),
                        finalizer_tracker=finalizer_tracker,
                        cancellation_binder=cancellation_binder,
                        cancellation_id=create_system_cancellation_id("plugin_worker.stop"),
                        owner="plugin_worker.stop",
                    )
                    ownership.stop_task = task
                tasks.append(task)
            return tasks

    async def retain_worker_resource(
        self, *, plugin_name: str, runtime: PluginWorkerRuntime | PluginWorkerAcquisition
    ) -> None:
        async with self._runtime_lock:
            if runtime.worker_id not in self._pending_worker_resources:
                self._pending_worker_resources[runtime.worker_id] = PluginWorkerResourceOwnership(
                    plugin_name, runtime
                )
            self._worker_id_to_plugin_name[runtime.worker_id] = plugin_name

    async def finalize_stop(
        self, plugin_name: str, runtime: PluginWorkerRuntime | PluginWorkerAcquisition
    ) -> bool:
        async with self._runtime_lock:
            ownership = self._pending_worker_resources.pop(runtime.worker_id, None)
            if self._workers.get(plugin_name) is runtime:
                self._workers.pop(plugin_name)
            self._worker_id_to_plugin_name.pop(runtime.worker_id, None)
            return ownership is not None

    async def register_loaded_runtime(
        self,
        *,
        plugin_name: str,
        runtime: PluginWorkerRuntime,
        expected_acquisition: PluginWorkerAcquisition | None = None,
    ) -> None:
        async with self._runtime_lock:
            if expected_acquisition is not None:
                acquisition = self._pending_worker_resources.get(runtime.worker_id)
                if (
                    acquisition is None
                    or acquisition.resource is not expected_acquisition
                    or acquisition.stop_task is not None
                ):
                    raise StateError("Plugin worker acquisition no longer owns a running worker.")
                self._pending_worker_resources.pop(runtime.worker_id)
            previous = self._workers.get(plugin_name)
            if previous is not None and previous is not runtime:
                if previous.worker_id not in self._pending_worker_resources:
                    self._pending_worker_resources[previous.worker_id] = (
                        PluginWorkerResourceOwnership(plugin_name, previous)
                    )
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
            ownership = self._pending_worker_resources.get(runtime.worker_id)
            if ownership is not None:
                task = ownership.stop_task
                if task is not None and not task.done():
                    return True
                self._pending_worker_resources.pop(runtime.worker_id, None)
                self._worker_id_to_plugin_name.pop(runtime.worker_id, None)
                if self._workers.get(plugin_name) is runtime:
                    self._workers.pop(plugin_name)
                return True
            return self._workers.get(plugin_name) is not runtime

    def record_cleanup_stage(self, worker_id: int, stage: str) -> None:
        ownership = self._pending_worker_resources.get(worker_id)
        if ownership is not None:
            ownership.cleanup_stage = stage

    def describe_worker_ownership(self, plugin_name: str) -> JSONDict:
        current_runtime = self._workers.get(plugin_name)
        return {
            "worker_generation": (
                current_runtime.worker_id if current_runtime is not None else None
            ),
            "retained_workers": [
                {
                    "worker_generation": worker_id,
                    "cleanup_stage": ownership.cleanup_stage,
                    "stop_active": ownership.stop_task is not None
                    and not ownership.stop_task.done(),
                }
                for worker_id, ownership in sorted(self._pending_worker_resources.items())
                if ownership.plugin_name == plugin_name
            ],
        }

    async def clear_all(self) -> None:
        async with self._runtime_lock:
            self._workers.clear()
            self._worker_id_to_plugin_name.clear()
            self._pending_worker_resources.clear()

    async def snapshot_plugin_names_for_shutdown(self) -> list[str]:
        async with self._runtime_lock:
            return list(
                dict.fromkeys(
                    [
                        *self._workers,
                        *(
                            ownership.plugin_name
                            for ownership in self._pending_worker_resources.values()
                        ),
                    ]
                )
            )

    async def snapshot_loaded_runtimes(self) -> list[PluginWorkerRuntime]:
        async with self._runtime_lock:
            return list(self._workers.values())
