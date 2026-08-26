"""SoAI - Parent-side plugin worker load execution [backend/plugins/worker/load_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import secrets

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_and_wait,
    uncancel_then_cleanup,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    ProcessError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.ipc.managed_worker import ManagedIpcWorkerDependencies
from core.ipc.multiplexed import MultiplexedIpcServer
from core.logging.trace import get_logger
from core.meta.paths import get_backend_root
from core.timing.constants import BACKGROUND_TIMEOUT_SEC
from core.types.json import JSONDict
from plugins.package_leases import (
    PluginPackageLease,
    create_plugin_package_lease,
    read_pid_create_time_ms,
    remove_plugin_package_lease,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.worker.bootstrap_payload import build_plugin_worker_bootstrap_payload
from plugins.worker.exit_watcher import PluginWorkerExitWatcher
from plugins.worker.host_router import PluginWorkerHostRouter
from plugins.worker.load_result import PluginWorkerLoadResult
from plugins.worker.proxy import ProxyPluginInstance
from plugins.worker.proxy_dependencies import ProxyPluginInstanceDependencies
from plugins.worker.runtime_registry import (
    PluginWorkerRuntime,
    PluginWorkerRuntimeRegistry,
)
from plugins.worker.worker_bootstrap import (
    build_plugin_worker_env,
    load_plugin_worker_surface,
)

__all__ = ("load_plugin_worker",)

LOGGER_NAME = "SoAI.plugins.worker.load_execution"
OPERATION_WORKER_LOAD_FAILURE_TERMINATE = "plugins.worker.controller.load_failure_terminate"
OPERATION_WORKER_LOAD_PLUGIN = "plugins.worker.controller.load_plugin"
OPERATION_WORKER_LOAD_PLUGIN_CANCELLED = "plugins.worker.controller.load_plugin_cancelled"
OPERATION_WORKER_REMOVE_TERMINATED_LEASE = (
    "plugins.worker.load_execution.remove_terminated_package_lease"
)
PLUGIN_WORKER_LOAD_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    InsufficientDiskSpaceError,
    OSError,
    ProcessError,
    StateError,
    ValidationError,
)


def _remove_terminated_worker_lease(
    lease_path: str,
    *,
    worker_id: int,
    plugin_name: str,
) -> None:
    try:
        remove_plugin_package_lease(lease_path)
    except OSError as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Terminated plugin worker package lease could not be removed.",
            operation=OPERATION_WORKER_REMOVE_TERMINATED_LEASE,
            details={"worker_id": worker_id, "plugin_name": plugin_name},
            level="error",
        )


async def load_plugin_worker(
    *,
    manager: PluginManagerRuntimeProtocol,
    registry: PluginWorkerRuntimeRegistry,
    server: MultiplexedIpcServer,
    host_router: PluginWorkerHostRouter,
    exit_watcher: PluginWorkerExitWatcher,
    plugin_name: str,
    plugin_package_root: str,
    plugin_entrypoint_path: str,
    plugin_file_hash: str,
    package_dependencies: list[str],
    plugin_config: JSONDict,
) -> PluginWorkerLoadResult:
    environment = await manager.dependencies.infrastructure.environment_manager.ensure_environment(
        plugin_name=plugin_name,
        package_dependencies=package_dependencies,
    )
    worker_id = await registry.allocate_worker_id(plugin_name=plugin_name)
    install_path = os.path.join(manager.paths.backends_directory, plugin_name)
    worker_secret = secrets.token_hex(32)
    try:
        await server.expect_worker_secret(worker_id, worker_secret=worker_secret)
    except asyncio.CancelledError:
        await uncancel_then_cleanup(registry.discard_worker_id(worker_id))
        await uncancel_then_cleanup(server.forget_worker_secret(worker_id))
        raise
    except PLUGIN_WORKER_LOAD_EXCEPTIONS:
        await registry.discard_worker_id(worker_id)
        await server.forget_worker_secret(worker_id)
        raise
    try:
        bootstrap = build_plugin_worker_bootstrap_payload(
            config=manager.dependencies.core.config,
            runtime_flags=manager.dependencies.infrastructure.runtime_flags,
            plugin_name=plugin_name,
            plugin_package_root=plugin_package_root,
            plugin_entrypoint_path=plugin_entrypoint_path,
            plugin_config=plugin_config,
            install_path=install_path,
        )
        worker = manager.dependencies.infrastructure.managed_ipc_worker_factory.create(
            ManagedIpcWorkerDependencies(
                worker_id=worker_id,
                argv=[environment.python_executable, "-m", "plugins.worker.main"],
                cwd=get_backend_root(),
                env=build_plugin_worker_env(
                    server=server,
                    worker_id=worker_id,
                    worker_secret=worker_secret,
                    bootstrap=bootstrap,
                ),
            ),
        )
    except PLUGIN_WORKER_LOAD_EXCEPTIONS:
        await registry.discard_worker_id(worker_id)
        await server.forget_worker_secret(worker_id)
        raise
    package_lease_path: str | None = None
    registered_runtime: PluginWorkerRuntime | None = None
    try:
        await worker.spawn(server=server, startup_timeout_sec=BACKGROUND_TIMEOUT_SEC)
        surface = await load_plugin_worker_surface(
            server=server,
            worker_id=worker_id,
            surface_timeout_sec=BACKGROUND_TIMEOUT_SEC,
        )
        proxy = ProxyPluginInstance(
            ProxyPluginInstanceDependencies(
                plugin_name=plugin_name,
                worker_id=worker_id,
                server=server,
                surface=surface,
                install_path=install_path,
                download_reservation_scope_factory=host_router.download_reservation_scope,
            ),
        )
        process = worker.process
        if process is None or process.pid is None:
            raise ProcessError(
                "Plugin worker process identity is unavailable after handshake.",
                operation=OPERATION_WORKER_LOAD_PLUGIN,
                details={"worker_id": worker_id, "plugin_name": plugin_name},
            )
        worker_create_time_ms = await asyncio.to_thread(
            read_pid_create_time_ms,
            process.pid,
        )
        if worker_create_time_ms is None:
            raise ProcessError(
                "Plugin worker process identity could not be verified after handshake.",
                operation=OPERATION_WORKER_LOAD_PLUGIN,
                details={"worker_id": worker_id, "plugin_name": plugin_name},
            )
        package_lease_path = await uncancel_and_wait(
            asyncio.to_thread(
                create_plugin_package_lease,
                temp_directory=manager.paths.temp_directory,
                lease=PluginPackageLease(
                    plugin_name=plugin_name,
                    archive_hash=plugin_file_hash,
                    worker_id=worker_id,
                    pid=process.pid,
                    create_time_ms=worker_create_time_ms,
                ),
                storage_manager=manager.dependencies.infrastructure.storage_manager,
            )
        )
        if current_task_has_pending_cancellation():
            raise asyncio.CancelledError
        runtime = PluginWorkerRuntime(
            worker_id=worker_id,
            worker=worker,
            proxy=proxy,
            package_lease_path=package_lease_path,
        )
        registered_runtime = runtime
        await registry.register_loaded_runtime(plugin_name=plugin_name, runtime=runtime)
        exit_watcher.watch(plugin_name=plugin_name, runtime=runtime)
        return PluginWorkerLoadResult(instance=proxy, surface=surface)
    except asyncio.CancelledError:
        worker_terminated = False
        try:
            await uncancel_then_cleanup(
                worker.terminate(operation="plugins.worker.load_plugin_cancelled")
            )
            host_router.release_worker_reservations(worker_id)
            worker_terminated = True
        except PLUGIN_WORKER_LOAD_EXCEPTIONS as termination_exception:
            host_router.release_worker_reservations(worker_id)
            log_exception(
                get_logger(LOGGER_NAME),
                termination_exception,
                message="Failed to terminate plugin worker after cancellation.",
                operation=OPERATION_WORKER_LOAD_PLUGIN_CANCELLED,
                details={"worker_id": worker_id, "plugin_name": plugin_name},
                level="warning",
            )
        if registered_runtime is not None:
            await uncancel_then_cleanup(
                registry.pop_loaded_runtime_if_current(
                    plugin_name=plugin_name,
                    runtime=registered_runtime,
                )
            )
        await uncancel_then_cleanup(registry.discard_worker_id(worker_id))
        await uncancel_then_cleanup(server.forget_worker_secret(worker_id))
        if package_lease_path is not None and worker_terminated:
            _remove_terminated_worker_lease(
                package_lease_path,
                worker_id=worker_id,
                plugin_name=plugin_name,
            )
        raise
    except PLUGIN_WORKER_LOAD_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            coerce_to_soai_error(
                exception,
                operation=OPERATION_WORKER_LOAD_PLUGIN,
                details={"worker_id": worker_id, "plugin_name": plugin_name},
            ),
            message="Plugin worker load failed; terminating worker process.",
            operation=OPERATION_WORKER_LOAD_PLUGIN,
            details={"worker_id": worker_id, "plugin_name": plugin_name},
            level="warning",
        )
        worker_terminated = False
        try:
            await uncancel_then_cleanup(
                worker.terminate(operation="plugins.worker.load_plugin_failed")
            )
            host_router.release_worker_reservations(worker_id)
            worker_terminated = True
        except PLUGIN_WORKER_LOAD_EXCEPTIONS as termination_exception:
            host_router.release_worker_reservations(worker_id)
            log_exception(
                get_logger(LOGGER_NAME),
                termination_exception,
                message="Failed to terminate plugin worker after load failure.",
                operation=OPERATION_WORKER_LOAD_FAILURE_TERMINATE,
                details={"worker_id": worker_id, "plugin_name": plugin_name},
                level="warning",
            )
        if registered_runtime is not None:
            await uncancel_then_cleanup(
                registry.pop_loaded_runtime_if_current(
                    plugin_name=plugin_name,
                    runtime=registered_runtime,
                )
            )
        await uncancel_then_cleanup(registry.discard_worker_id(worker_id))
        await uncancel_then_cleanup(server.forget_worker_secret(worker_id))
        if package_lease_path is not None and worker_terminated:
            _remove_terminated_worker_lease(
                package_lease_path,
                worker_id=worker_id,
                plugin_name=plugin_name,
            )
        raise
