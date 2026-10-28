"""SoAI - Plugin worker runtime policy failure retirement [backend/plugins/worker/runtime_policy_retirement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
    PluginWorkerControllerProtocol,
)
from plugins.worker.controller_faults import mark_worker_crashed
from plugins.worker.runtime_registry import (
    PluginWorkerRuntime,
)

__all__ = ("retire_runtime_after_policy_update_failure",)

LOGGER_NAME = "SoAI.plugins.worker.runtime_policy_retirement"
OPERATION_MARK_POLICY_FAILED_WORKER = (
    "plugins.worker.runtime_policy_retirement.mark_policy_failed_worker"
)


async def retire_runtime_after_policy_update_failure(
    *,
    manager: PluginManagerRuntimeProtocol,
    worker_controller: PluginWorkerControllerProtocol,
    runtime: PluginWorkerRuntime,
    primary_exception: Exception,
) -> None:
    plugin_name = runtime.proxy.plugin_name
    process = runtime.worker.process
    outcomes = await asyncio.gather(
        worker_controller.stop_plugin(plugin_name, expected_instance=runtime.proxy),
        return_exceptions=True,
    )
    cleanup_exception = outcomes[0]
    if isinstance(cleanup_exception, Exception):
        primary_exception.add_note(f"Policy-failed worker cleanup also failed: {cleanup_exception}")
    elif isinstance(cleanup_exception, BaseException):
        raise cleanup_exception
    async with manager.state.locks.load_lock:
        catalog = manager.state.catalog
        if catalog.loaded_plugin_instances.get(plugin_name) is not runtime.proxy:
            return
        catalog.loaded_plugin_instances.pop(plugin_name)
        catalog.loaded_plugin_surfaces.pop(plugin_name, None)
    returncode = process.returncode if process is not None else None
    try:
        await mark_worker_crashed(
            manager, plugin_name=plugin_name, returncode=returncode, expected_instance=runtime.proxy
        )
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
