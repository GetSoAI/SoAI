"""SoAI - Parent-side plugin worker load execution [backend/plugins/worker/load_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import secrets
import sys
from functools import partial

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    run_idempotent_current_task_operation,
    uncancel_and_wait,
    uncancel_then_cleanup,
)
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    ProcessError,
    StateError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_writes import atomic_create_text_content_exclusive
from core.ipc.managed_worker import ManagedIpcWorkerDependencies
from core.ipc.multiplexed import MultiplexedIpcServer
from core.logging.plugin_log_files import resolve_plugin_log_path
from core.logging.trace import get_logger
from core.meta.paths import get_backend_root
from core.system.native_runtime_probes import interpreter_probe_budget, native_phase_seconds
from core.timing.constants import EXTENDED_TIMEOUT_SEC, LONG_REQUEST_TIMEOUT_SEC
from core.types.json import JSONDict
from plugins.load_cleanup import preserve_plugin_load_failure
from plugins.package_leases import (
    PluginPackageLease,
    create_plugin_package_lease,
    read_pid_create_time_ms,
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
    PluginWorkerAcquisition,
    PluginWorkerRuntime,
    PluginWorkerRuntimeRegistry,
)
from plugins.worker.worker_bootstrap import (
    build_plugin_worker_env,
    load_plugin_worker_surface,
)

__all__ = ("load_plugin_worker",)

LOGGER_NAME = "SoAI.plugins.worker.load_execution"
OPERATION_WORKER_LOAD_PLUGIN = "plugins.worker.controller.load_plugin"
PLUGIN_WORKER_LOAD_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    InsufficientDiskSpaceError,
    OSError,
    ProcessError,
    StateError,
    ValidationError,
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
    acquisition_prepared = False
    try:
        install_path = os.path.join(manager.paths.backends_directory, plugin_name)
        worker_secret = secrets.token_hex(32)
        await server.expect_worker_secret(worker_id, worker_secret=worker_secret)
        bootstrap = build_plugin_worker_bootstrap_payload(
            config=manager.dependencies.core.config,
            runtime_flags=manager.dependencies.infrastructure.runtime_flags,
            plugin_name=plugin_name,
            plugin_package_root=plugin_package_root,
            plugin_entrypoint_path=plugin_entrypoint_path,
            plugin_config=plugin_config,
            install_path=install_path,
        )
        diagnostic_log_path = resolve_plugin_log_path(
            manager.dependencies.core.config,
            f"{plugin_name}.worker-{worker_id}-{secrets.token_hex(8)}.boot",
        )
        atomic_create_text_content_exclusive(
            diagnostic_log_path, "", parent_mode=0o700, file_mode=0o600
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
                diagnostic_log_path=diagnostic_log_path,
            ),
        )
        acquisition = PluginWorkerAcquisition(worker_id, worker)
        acquisition_prepared = True
    finally:
        primary_exception = sys.exception()
        if not acquisition_prepared:
            try:
                try:
                    await uncancel_then_cleanup(registry.discard_worker_id(worker_id))
                finally:
                    preserve_plugin_load_failure(primary_exception, sys.exception())
            finally:
                try:
                    await uncancel_then_cleanup(server.forget_worker_secret(worker_id))
                finally:
                    preserve_plugin_load_failure(primary_exception, sys.exception())
    transferred = False
    try:
        acquisition_task = await uncancel_and_wait(
            registry.begin_acquisition(
                plugin_name=plugin_name,
                acquisition=acquisition,
                operation=partial(
                    _acquire_worker_runtime,
                    manager=manager,
                    registry=registry,
                    server=server,
                    host_router=host_router,
                    exit_watcher=exit_watcher,
                    acquisition=acquisition,
                    plugin_name=plugin_name,
                    plugin_file_hash=plugin_file_hash,
                    install_path=install_path,
                    python_executable=environment.python_executable,
                ),
                finalizer_tracker=manager.dependencies.infrastructure.lifecycle.finalizer_tracker,
                cancellation_binder=manager.dependencies.infrastructure.lifecycle.cancellation_binder,
            )
        )
        if current_task_has_pending_cancellation():
            raise asyncio.CancelledError
        load_result = await asyncio.shield(acquisition_task)
        transferred = True
        return load_result
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
            details={
                "worker_id": worker_id,
                "plugin_name": plugin_name,
                "diagnostic_log_path": diagnostic_log_path,
            },
            level="warning",
        )
        raise
    finally:
        if not transferred:
            await _release_failed_worker_acquisition(manager, plugin_name, acquisition)


async def _acquire_worker_runtime(
    *,
    manager: PluginManagerRuntimeProtocol,
    registry: PluginWorkerRuntimeRegistry,
    server: MultiplexedIpcServer,
    host_router: PluginWorkerHostRouter,
    exit_watcher: PluginWorkerExitWatcher,
    acquisition: PluginWorkerAcquisition,
    plugin_name: str,
    plugin_file_hash: str,
    install_path: str,
    python_executable: str,
) -> PluginWorkerLoadResult:
    worker = acquisition.worker
    worker_id = acquisition.worker_id
    startup_budget = await asyncio.to_thread(
        interpreter_probe_budget,
        python_executable,
        ordinary_seconds=LONG_REQUEST_TIMEOUT_SEC + EXTENDED_TIMEOUT_SEC,
        environment=True,
    )
    await worker.spawn(
        server=server,
        startup_timeout_sec=native_phase_seconds(startup_budget, LONG_REQUEST_TIMEOUT_SEC),
    )
    surface = await load_plugin_worker_surface(
        server=server,
        worker_id=worker_id,
        surface_timeout_sec=native_phase_seconds(startup_budget, EXTENDED_TIMEOUT_SEC),
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
    lease_task = create_ephemeral_task(
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
        ),
        name=f"plugin-worker-lease-{worker_id}",
        log_exceptions=False,
    )
    package_lease_path = await run_idempotent_current_task_operation(
        lambda: asyncio.shield(lease_task)
    )
    acquisition.package_lease_path = package_lease_path
    if current_task_has_pending_cancellation():
        raise asyncio.CancelledError
    runtime = PluginWorkerRuntime(
        worker_id=worker_id,
        worker=worker,
        proxy=proxy,
        package_lease_path=package_lease_path,
    )
    await registry.register_loaded_runtime(
        plugin_name=plugin_name, runtime=runtime, expected_acquisition=acquisition
    )
    exit_watcher.watch(plugin_name=plugin_name, runtime=runtime)
    return PluginWorkerLoadResult(instance=proxy, surface=surface)


async def _release_failed_worker_acquisition(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    acquisition: PluginWorkerAcquisition,
) -> None:
    primary_exception = sys.exception()
    try:
        await uncancel_then_cleanup(
            manager.worker_controller.stop_plugin(
                plugin_name, expected_worker_id=acquisition.worker_id
            )
        )
    finally:
        preserve_plugin_load_failure(primary_exception, sys.exception())
