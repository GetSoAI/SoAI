"""SoAI - Startup stop-sweep recovery operations [backend/plugins/manager/startup_recovery_stop_sweep.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_float
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import await_publication_receipt
from core.logging.trace import get_logger
from core.runtime.backend_process_tracking import (
    BackendProcessIdentity,
    cleanup_backend_process_identities,
    normalize_backend_process_pids,
    resolve_backend_process_identities,
)
from core.runtime.backend_process_tracking_db import (
    cleanup_tracked_backend_processes_from_database,
)
from core.state.state_names import PLUGIN_STATE_STOPPED

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("perform_startup_backend_stop_sweep",)

LOGGER_NAME = "SoAI.plugins.manager.startup_recovery_stop_sweep"
OPERATION = "plugins.manager.startup_recovery.perform_startup_backend_stop_sweep"


async def perform_startup_backend_stop_sweep(manager: PluginManagerRuntimeProtocol) -> None:
    logger = get_logger(LOGGER_NAME)
    stop_sweep = manager.state.lifecycle.startup_recovery_stop_sweep
    if not stop_sweep:
        return
    timeout_sec = coerce_positive_float(
        manager.dependencies.core.config.get(
            "PLUGINS.RECOVERY.STARTUP_STOP_TIMEOUT_SEC",
            30.0,
        ),
        default=30.0,
        minimum=1.0,
        label="PLUGINS.RECOVERY.STARTUP_STOP_TIMEOUT_SEC",
        logger=logger,
    )
    plugin_names = sorted(stop_sweep)
    for plugin_name in plugin_names:
        instance = await _load_plugin_instance_for_stop(manager, plugin_name)
        if instance.PERSISTENT:
            logger.info(
                "Startup recovery: persistent plugin '%s' skipped stop sweep.",
                plugin_name,
            )
            stop_sweep.discard(plugin_name)
            continue
        record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
        supports_process_tracking = bool(record and record.get("supports_backend_process_tracking"))
        identities = (
            await manager.dependencies.databases.plugins.get_runtime_processes(plugin_name)
            if supports_process_tracking
            else []
        )
        stop_succeeded = False
        stop_exception: Exception | None = None
        if not identities:
            try:
                stop_succeeded = await _stop_plugin_instance(
                    instance,
                    plugin_name=plugin_name,
                    timeout_sec=timeout_sec,
                    logger=logger,
                )
            except TimeoutError as exception:
                stop_exception = exception
                log_exception(
                    logger,
                    exception,
                    message="Startup recovery: plugin stop timed out.",
                    operation=OPERATION,
                    details={"plugin_name": plugin_name},
                    level="warning",
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                stop_exception = exception
                log_exception(
                    logger,
                    exception,
                    message="Startup recovery: plugin stop failed.",
                    operation=OPERATION,
                    details={"plugin_name": plugin_name},
                    level="warning",
                )
            if not stop_succeeded:
                identities = await _resolve_backend_identities_from_instance(
                    manager,
                    plugin_name=plugin_name,
                    instance=instance,
                    supports_process_tracking=supports_process_tracking,
                    logger=logger,
                )
        if (not stop_succeeded) and (not identities):
            failure_detail = str(stop_exception) if stop_exception else "unknown"
            raise StateError(
                f"Startup recovery could not stop plugin '{plugin_name}': graceful stop failed ({failure_detail}) and no backend process identities were available for cleanup.",
            )
        if identities:
            cleanup_result = (
                await cleanup_tracked_backend_processes_from_database(
                    manager.dependencies.databases.plugins,
                    plugin_name=plugin_name,
                    logger=logger,
                )
                if supports_process_tracking
                else None
            )
            if cleanup_result is None:
                cleanup_result = await cleanup_backend_process_identities(
                    identities,
                    plugin_name=plugin_name,
                    logger=logger,
                )
            if not cleanup_result.succeeded:
                failure_detail = str(stop_exception) if stop_exception else "unknown"
                raise StateError(
                    f"Startup recovery could not stop plugin '{plugin_name}': backend process cleanup did not succeed ({failure_detail}).",
                )
        receipt = await manager.transition_plugin_manager_state(
            plugin_name,
            PLUGIN_STATE_STOPPED,
            "Startup recovery: stop sweep completed.",
        )
        await await_publication_receipt(receipt)
        stop_sweep.discard(plugin_name)
    stop_sweep.clear()


async def _load_plugin_instance_for_stop(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> PluginInstanceProtocol:
    try:
        return await manager.require_loaded_plugin(plugin_name, auto_load=True)
    except RECOVERABLE_EXCEPTIONS as exception:
        raise StateError(
            f"Startup recovery stop sweep failed: plugin instance '{plugin_name}' could not be loaded.",
        ) from exception


async def _stop_plugin_instance(
    instance: PluginInstanceProtocol,
    *,
    plugin_name: str,
    timeout_sec: float,
    logger: LoggerProtocol,
) -> bool:
    try:
        stop_result = await asyncio.wait_for(instance.stop(), timeout=timeout_sec)
        stop_succeeded = bool(stop_result)
        if stop_succeeded:
            logger.info("Startup recovery: plugin '%s' stopped gracefully.", plugin_name)
        else:
            logger.warning(
                "Startup recovery: plugin '%s' returned unsuccessful stop result.",
                plugin_name,
            )
        return stop_succeeded
    except TimeoutError:
        logger.warning(
            "Startup recovery: plugin '%s' failed to stop gracefully (timeout=%.3fs).",
            plugin_name,
            timeout_sec,
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Startup recovery: plugin '{plugin_name}' failed to stop gracefully.",
            operation=OPERATION,
            level="warning",
            details={"plugin_name": plugin_name, "timeout_sec": timeout_sec},
        )
        raise


async def _resolve_backend_identities_from_instance(
    manager: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    instance: PluginInstanceProtocol,
    supports_process_tracking: bool,
    logger: LoggerProtocol,
) -> list[BackendProcessIdentity]:
    raw_pids = await instance.get_backend_process_pids()
    pids = normalize_backend_process_pids(raw_pids)
    if not pids:
        return []
    resolved = resolve_backend_process_identities(
        pids,
        plugin_name=plugin_name,
        logger=logger,
    )
    if supports_process_tracking and resolved:
        await manager.dependencies.databases.plugins.set_runtime_processes(
            plugin_name,
            resolved,
        )
    return resolved
