"""SoAI - Scheduler plugin action failure modeling [backend/orchestrator/scheduling/plugin_action_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.error_types import ErrorType
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_ERROR,
    ORCH_STATE_QUARANTINED,
)
from core.state.state_transition_sets import PLUGIN_MANAGER_TRANSIENT_STATES

__all__ = (
    "PluginActionFailure",
    "build_prohibitive_state_failure",
)


@dataclass(frozen=True, slots=True)
class PluginActionFailure:
    message: str
    operator_reason: str
    error_type: ErrorType


def build_prohibitive_state_failure(plugin_name: str, plugin_status: str) -> PluginActionFailure:
    error_type = _resolve_prohibitive_state_error_type(plugin_status)
    message = _resolve_prohibitive_state_user_message(plugin_status)
    operator_reason = f"Plugin '{plugin_name}' is in a prohibitive state: {plugin_status}"
    return PluginActionFailure(
        message=message,
        operator_reason=operator_reason,
        error_type=error_type,
    )


def _resolve_prohibitive_state_error_type(plugin_status: str) -> ErrorType:
    if plugin_status == ORCH_STATE_ERROR:
        return ErrorType.PLUGIN_UNAVAILABLE
    if plugin_status == ORCH_STATE_QUARANTINED:
        return ErrorType.PLUGIN_QUARANTINED
    if plugin_status == ORCH_STATE_DISABLED:
        return ErrorType.PLUGIN_DISABLED
    if plugin_status in PLUGIN_MANAGER_TRANSIENT_STATES:
        return ErrorType.PLUGIN_INITIALIZING
    return ErrorType.SERVER_ERROR


def _resolve_prohibitive_state_user_message(plugin_status: str) -> str:
    if plugin_status == ORCH_STATE_ERROR:
        return "The model backend hit a transient error and is recovering. Please retry in a few seconds."
    if plugin_status == ORCH_STATE_QUARANTINED:
        return "This model's backend has been temporarily quarantined after repeated failures. It will retry automatically."
    if plugin_status == ORCH_STATE_DISABLED:
        return "This model's backend is disabled."
    if plugin_status in PLUGIN_MANAGER_TRANSIENT_STATES:
        return "The model backend is initializing. Please retry in a moment."
    return "The model backend is currently unavailable."
