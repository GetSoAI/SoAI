"""SoAI - Plugin activation target-state resolution [backend/orchestrator/lifecycle/user_commands/plugin_activation_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.plugins.persistent_runtime_truth import (
    get_plugin_status_payload,
    plugin_status_reports_installed,
    resolve_persistent_runtime_state,
)
from core.state.state_names import (
    ORCH_STATE_ERROR,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_STOPPED,
    PluginRuntimeStateName,
)

if TYPE_CHECKING:
    from core.plugins.protocols import PluginManagerProtocol

__all__ = (
    "PluginActivationTransition",
    "resolve_clear_quarantine_activation_transition_or_none",
    "resolve_plugin_activation_transition",
)

CLEAR_QUARANTINE_OPERATION = "orchestrator.handle_clear_quarantine.persistent"
CLEAR_QUARANTINE_BASE_REASON = "Quarantine cleared by user."


@dataclass(frozen=True, slots=True)
class PluginActivationTransition:
    target_state: PluginRuntimeStateName
    reason: str


async def _resolve_activation_target(
    *,
    plugin_manager: PluginManagerProtocol,
    plugin_name: str,
    attempt_activate: bool,
    failure_state: PluginRuntimeStateName,
    operation: str,
    logger: TraceLogger,
) -> tuple[PluginRuntimeStateName, str]:
    instance = await plugin_manager.require_loaded_plugin(plugin_name, auto_load=True)
    if instance.PERSISTENT:
        target_state, persistent_reason, _status_payload = await resolve_persistent_runtime_state(
            instance,
            attempt_activate=attempt_activate,
            failure_state=failure_state,
            operation=operation,
            logger=logger,
        )
        return target_state, persistent_reason
    if instance.SUPPORTS_BACKEND_INSTALLATION:
        status_payload = await get_plugin_status_payload(
            instance,
            operation=f"{operation}.get_status",
            logger=logger,
        )
        installed = plugin_status_reports_installed(
            status_payload,
            operation=f"{operation}.installed",
            logger=logger,
            default=False,
        )
        if not installed:
            return PLUGIN_STATE_BACKEND_NOT_INSTALLED, "Backend not installed."
    return PLUGIN_STATE_STOPPED, ""


async def resolve_plugin_activation_transition(
    *,
    plugin_manager: PluginManagerProtocol,
    plugin_name: str,
    attempt_activate: bool,
    failure_state: PluginRuntimeStateName,
    operation: str,
    logger: TraceLogger,
    base_reason: str,
) -> PluginActivationTransition:
    target_state, detail = await _resolve_activation_target(
        plugin_manager=plugin_manager,
        plugin_name=plugin_name,
        attempt_activate=attempt_activate,
        failure_state=failure_state,
        operation=operation,
        logger=logger,
    )
    return PluginActivationTransition(
        target_state=target_state,
        reason=f"{base_reason} {detail}".strip() if detail else base_reason,
    )


async def resolve_clear_quarantine_activation_transition_or_none(
    *,
    plugin_manager: PluginManagerProtocol,
    plugin_name: str,
    logger: TraceLogger,
) -> PluginActivationTransition | None:
    try:
        return await resolve_plugin_activation_transition(
            plugin_manager=plugin_manager,
            plugin_name=plugin_name,
            attempt_activate=True,
            failure_state=ORCH_STATE_ERROR,
            operation=CLEAR_QUARANTINE_OPERATION,
            logger=logger,
            base_reason=CLEAR_QUARANTINE_BASE_REASON,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=(
                f"Could not determine target state while clearing quarantine for '{plugin_name}'."
            ),
            operation=CLEAR_QUARANTINE_OPERATION,
        )
        return None
