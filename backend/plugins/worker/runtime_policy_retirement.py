"""SoAI - Plugin worker runtime policy failure retirement [backend/plugins/worker/runtime_policy_retirement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.ipc.multiplexed import MultiplexedIpcServer
from core.logging.trace import get_logger
from plugins.package_leases import remove_plugin_package_lease
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.worker.controller_faults import mark_worker_crashed
from plugins.worker.exit_watcher import PluginWorkerExitWatcher
from plugins.worker.host_router import PluginWorkerHostRouter
from plugins.worker.runtime_registry import (
    PluginWorkerRuntime,
    PluginWorkerRuntimeRegistry,
)

__all__ = ("retire_runtime_after_policy_update_failure",)

LOGGER_NAME = "SoAI.plugins.worker.runtime_policy_retirement"
OPERATION_RETIRE_POLICY_FAILED_WORKER = (
    "plugins.worker.runtime_policy_retirement.retire_policy_failed_worker"
)
OPERATION_MARK_POLICY_FAILED_WORKER = (
    "plugins.worker.runtime_policy_retirement.mark_policy_failed_worker"
)
OPERATION_REMOVE_POLICY_FAILED_WORKER_LEASE = (
    "plugins.worker.runtime_policy_retirement.remove_package_lease"
)
POLICY_RETIREMENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    ProcessError,
)


async def retire_runtime_after_policy_update_failure(
    *,
    manager: PluginManagerRuntimeProtocol,
    registry: PluginWorkerRuntimeRegistry,
    server: MultiplexedIpcServer,
    exit_watcher: PluginWorkerExitWatcher,
    host_router: PluginWorkerHostRouter,
    runtime: PluginWorkerRuntime,
) -> None:
    plugin_name = runtime.proxy.plugin_name
    process = runtime.worker.process
    await exit_watcher.cancel(runtime.worker_id)
    popped = await registry.pop_loaded_runtime_if_current(
        plugin_name=plugin_name,
        runtime=runtime,
    )
    if popped:
        async with manager.state.locks.load_lock:
            catalog = manager.state.catalog
            catalog.loaded_plugin_instances.pop(plugin_name, None)
            catalog.loaded_plugin_surfaces.pop(plugin_name, None)
    await server.disconnect_worker(runtime.worker_id)
    await server.forget_worker_secret(runtime.worker_id)
    terminated = True
    try:
        await runtime.worker.terminate(operation="plugins.worker.update_runtime_flags_failed")
    except POLICY_RETIREMENT_EXCEPTIONS as exception:
        terminated = False
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to terminate plugin worker after runtime policy update failure.",
            operation=OPERATION_RETIRE_POLICY_FAILED_WORKER,
            details={"worker_id": runtime.worker_id, "plugin_name": plugin_name},
            level="error",
        )
    returncode = process.returncode if process is not None else None
    if terminated:
        host_router.release_worker_reservations(runtime.worker_id)
        try:
            remove_plugin_package_lease(runtime.package_lease_path)
        except OSError as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Retired plugin worker package lease could not be removed.",
                operation=OPERATION_REMOVE_POLICY_FAILED_WORKER_LEASE,
                details={"worker_id": runtime.worker_id, "plugin_name": plugin_name},
                level="error",
            )
    if not popped:
        return
    try:
        await mark_worker_crashed(manager, plugin_name=plugin_name, returncode=returncode)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to mark runtime-policy-failed plugin worker unavailable.",
            operation=OPERATION_MARK_POLICY_FAILED_WORKER,
            details={"worker_id": runtime.worker_id, "plugin_name": plugin_name},
            level="error",
        )
        return
