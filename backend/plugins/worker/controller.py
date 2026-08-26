"""SoAI - Parent-side plugin worker lifecycle controller [backend/plugins/worker/controller.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.locking import async_guarded_file_lock
from core.logging.trace import get_logger
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.types.json import JSONDict
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
    PluginWorkerRuntime,
    PluginWorkerRuntimeRegistry,
    PluginWorkerRuntimeRegistryDependencies,
)

__all__ = (
    "PluginWorkerController",
    "PluginWorkerRuntime",
)

LOGGER_NAME = "SoAI.plugins.worker.controller"
OPERATION_WORKER_SHUTDOWN_TERMINATE = "plugins.worker.controller.shutdown_terminate"
OPERATION_WORKER_SHUTDOWN_REMOVE_LEASE = "plugins.worker.controller.shutdown_remove_package_lease"
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
                stopping_worker_ids=set(),
                stopping_plugin_names=set(),
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
        logger = get_logger(LOGGER_NAME)
        first_exception: BaseException | None = None
        runtimes = await self._registry.snapshot_runtimes_for_shutdown()
        try:
            for runtime in runtimes:
                try:
                    await runtime.worker.terminate(operation="plugins.worker.shutdown")
                    self._host_router.release_worker_reservations(runtime.worker_id)
                except PLUGIN_WORKER_FAILURE_EXCEPTIONS as exception:
                    self._host_router.release_worker_reservations(runtime.worker_id)
                    if first_exception is None:
                        first_exception = exception
                    log_exception(
                        logger,
                        exception,
                        message="Failed to terminate plugin worker during shutdown.",
                        operation=OPERATION_WORKER_SHUTDOWN_TERMINATE,
                        details={"worker_id": runtime.worker_id},
                        level="warning",
                    )
                    continue
                try:
                    remove_plugin_package_lease(runtime.package_lease_path)
                except OSError as exception:
                    if first_exception is None:
                        first_exception = exception
                    log_exception(
                        logger,
                        exception,
                        message="Failed to remove terminated plugin worker package lease during shutdown.",
                        operation=OPERATION_WORKER_SHUTDOWN_REMOVE_LEASE,
                        details={"worker_id": runtime.worker_id},
                        level="error",
                    )
        finally:
            await self._exit_watcher.cancel_all()
            await self._registry.clear_all()
            await self._server.shutdown()
        if first_exception is not None:
            raise first_exception

    async def stop_plugin(self, plugin_name: str) -> None:
        runtime = await self._registry.begin_stop(plugin_name)
        if runtime is not None:
            terminated = False
            lease_removal_error: OSError | None = None
            try:
                await runtime.worker.terminate(operation="plugins.worker.stop_plugin")
                self._host_router.release_worker_reservations(runtime.worker_id)
                terminated = True
            except PLUGIN_WORKER_FAILURE_EXCEPTIONS:
                await self._registry.restore_after_stop_failure(
                    plugin_name=plugin_name,
                    runtime=runtime,
                )
                raise
            try:
                remove_plugin_package_lease(runtime.package_lease_path)
            except OSError as exception:
                lease_removal_error = exception
            finally:
                if terminated:
                    await self._server.disconnect_worker(runtime.worker_id)
                    should_cancel_monitor = await self._registry.finalize_stop(
                        plugin_name,
                        runtime,
                    )
                    await self._server.forget_worker_secret(runtime.worker_id)
                    if should_cancel_monitor:
                        await self._exit_watcher.cancel(runtime.worker_id)
            if lease_removal_error is not None:
                raise StateError(
                    "Plugin worker terminated but its package cache lease could not be removed.",
                    operation="plugins.worker.stop_plugin.remove_package_lease",
                    details={
                        "plugin_name": plugin_name,
                        "worker_id": runtime.worker_id,
                        "lease_path": runtime.package_lease_path,
                    },
                ) from lease_removal_error
        else:
            await self._registry.cancel_stop_flag(plugin_name)

    async def delete_plugin_environment(self, plugin_name: str) -> None:
        await self._manager.dependencies.infrastructure.environment_manager.delete_environment(
            plugin_name
        )

    async def update_runtime_flags(self, runtime_flags: RuntimeFlagsViewProtocol) -> None:
        runtimes = await self._registry.snapshot_loaded_runtimes()
        first_exception: Exception | None = None
        for runtime in runtimes:
            try:
                await runtime.proxy.update_runtime_flags(runtime_flags)
            except PLUGIN_WORKER_FAILURE_EXCEPTIONS as exception:
                if first_exception is None:
                    first_exception = exception
                log_exception(
                    get_logger(LOGGER_NAME),
                    exception,
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
                    registry=self._registry,
                    server=self._server,
                    exit_watcher=self._exit_watcher,
                    host_router=self._host_router,
                    runtime=runtime,
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
        async with async_guarded_file_lock(cache_lock_path, timeout=120):
            await self.stop_plugin(plugin_name)
            return await load_plugin_worker(
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
