"""SoAI - Parent-side plugin worker lifecycle controller [backend/plugins/worker/controller.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from sys import exception

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.locking import async_guarded_file_lock
from core.logging.trace import get_logger
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.types.json import JSONDict
from plugins.load_cleanup import preserve_plugin_load_failure
from plugins.package_leases import remove_plugin_package_lease
from plugins.package_paths import get_plugin_package_cache_lock_target
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.worker.exit_watcher import PluginWorkerExitWatcher
from plugins.worker.host_router import PluginWorkerHostRouter
from plugins.worker.ipc_server_factory import build_plugin_worker_ipc_server
from plugins.worker.load_execution import load_plugin_worker
from plugins.worker.load_result import PluginWorkerLoadResult
from plugins.worker.runtime_policy_retirement import (
    retire_runtime_after_policy_update_failure,
)
from plugins.worker.runtime_registry import (
    PluginWorkerAcquisition,
    PluginWorkerRuntime,
    PluginWorkerRuntimeRegistry,
    PluginWorkerRuntimeRegistryDependencies,
)

__all__ = (
    "PluginWorkerController",
    "PluginWorkerRuntime",
)

LOGGER_NAME = "SoAI.plugins.worker.controller"
OPERATION_WORKER_UPDATE_RUNTIME_FLAGS = "plugins.worker.controller.update_runtime_flags"
PLUGIN_WORKER_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    ProcessError,
)


class PluginWorkerController:
    def __init__(self, manager: PluginManagerRuntimeProtocol) -> None:
        self._manager = manager
        self._registry = PluginWorkerRuntimeRegistry(
            PluginWorkerRuntimeRegistryDependencies(
                runtime_lock=asyncio.Lock(),
                workers={},
                worker_id_to_plugin_name={},
                pending_worker_resources={},
                next_worker_id=1,
            ),
        )
        self._host_router = PluginWorkerHostRouter(
            manager,
            resolve_plugin_name_for_worker=self._registry.resolve_plugin_name_for_worker,
        )
        self._server = build_plugin_worker_ipc_server(
            encoding_pool=manager.dependencies.infrastructure.ipc_encoding_pool,
            config=manager.dependencies.core.config,
            host_request_handler=self._host_router.handle_request,
        )
        self._exit_watcher = PluginWorkerExitWatcher(
            manager=self._manager,
            registry=self._registry,
            server=self._server,
            release_worker_reservations=self._host_router.release_worker_reservations,
        )

    async def start(self) -> None:
        await self._server.start()

    async def shutdown(self) -> None:
        plugin_names = await self._registry.snapshot_plugin_names_for_shutdown()
        stop_operations = [self.stop_plugin(plugin_name) for plugin_name in plugin_names]
        outcomes = await uncancel_then_cleanup(
            asyncio.gather(*stop_operations, return_exceptions=True)
        )
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                raise outcome
        await self._exit_watcher.cancel_all()
        await self._server.shutdown()

    async def stop_plugin(
        self,
        plugin_name: str,
        *,
        expected_instance: PluginInstanceProtocol | None = None,
        expected_worker_id: int | None = None,
    ) -> None:
        tasks = await self._registry.begin_stop(
            plugin_name,
            expected_instance=expected_instance,
            expected_worker_id=expected_worker_id,
            stop_operation=self._stop_runtime,
            finalizer_tracker=self._manager.dependencies.infrastructure.lifecycle.finalizer_tracker,
            cancellation_binder=self._manager.dependencies.infrastructure.lifecycle.cancellation_binder,
        )
        outcomes = await uncancel_then_cleanup(asyncio.gather(*tasks, return_exceptions=True))
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                raise outcome

    async def _stop_runtime(
        self, plugin_name: str, runtime: PluginWorkerRuntime | PluginWorkerAcquisition
    ) -> None:
        stopped = False
        try:
            if (
                isinstance(runtime, PluginWorkerAcquisition)
                and runtime.acquisition_task is not None
            ):
                self._registry.record_cleanup_stage(runtime.worker_id, "acquisition_cancellation")
                if not runtime.acquisition_task.done():
                    runtime.acquisition_task.cancel()
                await uncancel_then_cleanup(
                    asyncio.gather(runtime.acquisition_task, return_exceptions=True)
                )
            self._registry.record_cleanup_stage(runtime.worker_id, "worker_termination")
            await runtime.worker.terminate(operation="plugins.worker.stop_plugin")
            self._registry.record_cleanup_stage(runtime.worker_id, "ipc_disconnection")
            await self._server.disconnect_worker(runtime.worker_id)
            await self._server.forget_worker_secret(runtime.worker_id)
            self._registry.record_cleanup_stage(runtime.worker_id, "exit_watcher_cancellation")
            await self._exit_watcher.cancel(runtime.worker_id)
            self._host_router.release_worker_reservations(runtime.worker_id)
            self._registry.record_cleanup_stage(runtime.worker_id, "package_lease_removal")
            try:
                if runtime.package_lease_path is not None:
                    remove_plugin_package_lease(runtime.package_lease_path)
            except OSError as lease_exception:
                raise StateError(
                    "Plugin worker terminated but its package cache lease could not be removed.",
                    operation="plugins.worker.stop_plugin.remove_package_lease",
                    details={
                        "plugin_name": plugin_name,
                        "worker_id": runtime.worker_id,
                        "lease_path": runtime.package_lease_path,
                    },
                ) from lease_exception
            await self._registry.finalize_stop(plugin_name, runtime)
            stopped = True
        finally:
            if not stopped:
                await uncancel_then_cleanup(
                    self._registry.retain_worker_resource(plugin_name=plugin_name, runtime=runtime)
                )

    def describe_worker_ownership(self, plugin_name: str) -> JSONDict:
        return self._registry.describe_worker_ownership(plugin_name)

    async def delete_plugin_environment(self, plugin_name: str) -> None:
        await self.stop_plugin(plugin_name)
        await self._manager.dependencies.infrastructure.environment_manager.delete_environment(
            plugin_name
        )

    async def update_runtime_flags(self, runtime_flags: RuntimeFlagsViewProtocol) -> None:
        runtimes = await self._registry.snapshot_loaded_runtimes()
        first_exception: Exception | None = None
        for runtime in runtimes:
            try:
                await runtime.proxy.update_runtime_flags(runtime_flags)
            except PLUGIN_WORKER_FAILURE_EXCEPTIONS as policy_exception:
                if first_exception is None:
                    first_exception = policy_exception
                log_exception(
                    get_logger(LOGGER_NAME),
                    policy_exception,
                    message="Failed to update plugin worker runtime flags.",
                    operation=OPERATION_WORKER_UPDATE_RUNTIME_FLAGS,
                    details={
                        "plugin_name": runtime.proxy.plugin_name,
                        "worker_id": runtime.worker_id,
                    },
                    level="warning",
                )
                await retire_runtime_after_policy_update_failure(
                    manager=self._manager,
                    worker_controller=self,
                    runtime=runtime,
                    primary_exception=policy_exception,
                )
        if first_exception is not None:
            raise first_exception

    async def load_plugin(
        self,
        *,
        plugin_name: str,
        plugin_package_root: str,
        plugin_entrypoint_path: str,
        plugin_file_hash: str,
        package_dependencies: list[str],
        plugin_config: JSONDict,
    ) -> PluginWorkerLoadResult:
        cache_lock_target = get_plugin_package_cache_lock_target(
            self._manager.paths.temp_directory,
            plugin_name,
        )
        cache_lock_path = self._manager.dependencies.infrastructure.config_manager.get_lock_path(
            cache_lock_target
        )
        load_result: PluginWorkerLoadResult | None = None
        transferred = False
        try:
            async with async_guarded_file_lock(cache_lock_path, timeout=120):
                await self.stop_plugin(plugin_name)
                load_result = await load_plugin_worker(
                    manager=self._manager,
                    registry=self._registry,
                    server=self._server,
                    host_router=self._host_router,
                    exit_watcher=self._exit_watcher,
                    plugin_name=plugin_name,
                    plugin_package_root=plugin_package_root,
                    plugin_entrypoint_path=plugin_entrypoint_path,
                    plugin_file_hash=plugin_file_hash,
                    package_dependencies=package_dependencies,
                    plugin_config=plugin_config,
                )
            transferred = True
            return load_result
        finally:
            primary_exception = exception()
            if load_result is not None and not transferred:
                try:
                    await uncancel_then_cleanup(
                        self.stop_plugin(plugin_name, expected_instance=load_result.instance)
                    )
                finally:
                    preserve_plugin_load_failure(primary_exception, exception())
