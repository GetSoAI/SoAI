"""SoAI - Plugin initial-state resolution on startup [backend/plugins/manager/initial_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.plugins.persistent_runtime_truth import (
    get_plugin_status_payload,
    plugin_status_reports_installed,
    resolve_persistent_runtime_state,
)
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_ERROR,
    ORCH_STATE_QUARANTINED,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_STOPPED,
)
from plugins.clone.clone_committed_integrity import is_clone_integrity_quarantined
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.state.state_names import PluginRuntimeStateName
    from core.types.json import JSONDict

__all__ = (
    "compute_initial_state",
    "get_initial_plugin_manager_state",
    "log_initial_state_resolution",
)

LOGGER_NAME = "SoAI.plugins.manager.initial_state"
OPERATION = "plugin_manager.get_initial_plugin_manager_state"


def log_initial_state_resolution(
    instance: PluginInstanceProtocol,
    state_details: str,
    initial_state: PluginRuntimeStateName,
) -> PluginRuntimeStateName:
    logger = get_logger(LOGGER_NAME)
    logger.info(
        "Initial state for '%s': %s (resolved_state=%s).",
        instance.plugin_name,
        state_details,
        initial_state,
    )
    return initial_state


def _resolve_plugin_version_soaiplugin(instance: PluginInstanceProtocol) -> str:
    version = instance.VERSION_SOAIPLUGIN
    return str(version) if isinstance(version, str) and version else "Unknown"


async def get_initial_plugin_manager_state(
    instance: PluginInstanceProtocol | None,
    *,
    attempt_activate_persistent: bool = False,
) -> PluginRuntimeStateName:
    logger = get_logger(LOGGER_NAME)
    if instance is None:
        return PLUGIN_STATE_NOT_DETECTED
    try:
        logger.debug(
            "Querying initial installation status for '%s' from the plugin instance...",
            instance.plugin_name,
        )
        status_payload = await get_plugin_status_payload(
            instance,
            operation="plugin_manager.get_initial_plugin_manager_state.get_status",
            logger=logger,
            raise_on_error=True,
        )
        is_installed = plugin_status_reports_installed(
            status_payload,
            operation="plugin_manager.get_initial_plugin_manager_state.parse_installed",
            logger=logger,
            default=(not instance.SUPPORTS_BACKEND_INSTALLATION),
        )
        detail_parts = [
            f"installed={is_installed}",
            f"version_soaiplugin={status_payload.get('version_soaiplugin') or _resolve_plugin_version_soaiplugin(instance)}",
        ]
        if (bv := status_payload.get("backend_version")) is not None:
            detail_parts.append(f"backend_version={bv}")
        if pv := status_payload.get("path"):
            detail_parts.append(f"path={pv}")
        if sf := status_payload.get("status"):
            detail_parts.append(f"status={sf}")
        if ef := status_payload.get("error"):
            detail_parts.append(f"error={ef}")
        details_text = ", ".join(detail_parts)
        if instance.PERSISTENT:
            initial_state, persistent_reason, _ = await resolve_persistent_runtime_state(
                instance,
                attempt_activate=attempt_activate_persistent,
                failure_state=ORCH_STATE_ERROR,
                operation="plugin_manager.get_initial_plugin_manager_state.persistent",
                logger=logger,
                status_payload=status_payload,
            )
            return log_initial_state_resolution(
                instance,
                f"persistent plugin, {details_text}, reason={persistent_reason}",
                initial_state,
            )
        if not instance.SUPPORTS_BACKEND_INSTALLATION:
            return log_initial_state_resolution(
                instance,
                f"non-installable plugin, {details_text}",
                PLUGIN_STATE_STOPPED,
            )
        initial_state = PLUGIN_STATE_STOPPED if is_installed else PLUGIN_STATE_BACKEND_NOT_INSTALLED
        return log_initial_state_resolution(instance, details_text, initial_state)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Error checking initial install state for {instance.plugin_name}",
            operation=OPERATION,
            details={"plugin": instance.plugin_name},
        )
        return PLUGIN_STATE_LOAD_ERROR


async def compute_initial_state(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    instance: PluginInstanceProtocol,
    existing_record: JSONDict | None,
) -> tuple[PluginRuntimeStateName, str]:
    logger = get_logger(LOGGER_NAME)
    persisted_state = existing_record.get("state") if existing_record else None
    reset_circuit_breaker_quarantine = False
    if existing_record and existing_record.get("state") == ORCH_STATE_DISABLED:
        logger.info(
            "Persisted disabled state detected for '%s'. Maintaining DISABLED state on startup.",
            plugin_name,
        )
        return (
            ORCH_STATE_DISABLED,
            "Plugin remains disabled per persisted runtime state.",
        )
    if existing_record and existing_record.get("state") == ORCH_STATE_QUARANTINED:
        if await is_clone_integrity_quarantined(manager, plugin_name):
            logger.warning(
                "Clone integrity quarantine detected for '%s'. Maintaining QUARANTINED state on startup.",
                plugin_name,
            )
            return (
                ORCH_STATE_QUARANTINED,
                "Plugin remains quarantined for clone integrity recovery.",
            )
        reset_circuit_breaker_quarantine = True
        logger.info(
            "Resetting circuit-breaker quarantine for '%s' on startup.",
            plugin_name,
        )
    initial_state = await get_initial_plugin_manager_state(
        instance,
        attempt_activate_persistent=True,
    )
    if reset_circuit_breaker_quarantine:
        return (
            initial_state,
            "Startup recovery: resetting circuit-breaker quarantine.",
        )
    if persisted_state in manager.policy.startup_reset_states:
        logger.info(
            "Resetting '%s' from %s to %s on startup (fresh start policy).",
            plugin_name,
            persisted_state,
            initial_state,
        )
        return (
            initial_state,
            "Startup recovery: resetting persisted error state.",
        )
    return (initial_state, "Plugin state determined from filesystem.")
