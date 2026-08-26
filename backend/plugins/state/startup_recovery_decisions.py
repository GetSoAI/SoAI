"""SoAI - Plugin startup recovery decision helpers [backend/plugins/state/startup_recovery_decisions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.state.state_names import (
    ORCH_STATE_ERROR,
    ORCH_STATE_IDLE,
    ORCH_STATE_LOADING,
    ORCH_STATE_PROCESSING,
    ORCH_STATE_READY,
    ORCH_STATE_READY_DIRTY,
    ORCH_STATE_READY_PENDING_DISPATCH,
    ORCH_STATE_STARTING,
    ORCH_STATE_STOPPING,
    ORCH_STATE_UNKNOWN,
    PLUGIN_STATE_BACKEND_INSTALLING,
    PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
    PLUGIN_STATE_BACKEND_UPDATING,
    PLUGIN_STATE_DELETE_ERROR,
    PLUGIN_STATE_DELETING,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_REMOVING_BACKEND,
    PLUGIN_STATE_UPDATE_ERROR,
)

if TYPE_CHECKING:
    from core.state.state_names import PluginRuntimeStateName

__all__ = (
    "STARTUP_INTERRUPTED_ACTION_STATES",
    "STARTUP_STALE_RUNTIME_STATES",
    "resolve_startup_interrupted_action_recovery_state",
)

STARTUP_INTERRUPTED_ACTION_STATES: frozenset[str] = frozenset(
    {
        PLUGIN_STATE_BACKEND_INSTALLING,
        PLUGIN_STATE_BACKEND_UPDATING,
        PLUGIN_STATE_REMOVING_BACKEND,
        PLUGIN_STATE_DELETING,
    },
)
STARTUP_STALE_RUNTIME_STATES: frozenset[str] = frozenset(
    {
        ORCH_STATE_UNKNOWN,
        ORCH_STATE_STARTING,
        ORCH_STATE_LOADING,
        ORCH_STATE_READY_PENDING_DISPATCH,
        ORCH_STATE_READY,
        ORCH_STATE_READY_DIRTY,
        ORCH_STATE_PROCESSING,
        ORCH_STATE_IDLE,
        ORCH_STATE_STOPPING,
        ORCH_STATE_ERROR,
    },
)


def resolve_startup_interrupted_action_recovery_state(
    plugin_name: str,
    state: str,
    *,
    operation: str,
    unhandled_message: str,
) -> PluginRuntimeStateName:
    if state == PLUGIN_STATE_BACKEND_INSTALLING:
        return PLUGIN_STATE_INSTALL_ERROR
    if state == PLUGIN_STATE_BACKEND_UPDATING:
        return PLUGIN_STATE_UPDATE_ERROR
    if state == PLUGIN_STATE_REMOVING_BACKEND:
        return PLUGIN_STATE_BACKEND_UNINSTALL_ERROR
    if state == PLUGIN_STATE_DELETING:
        return PLUGIN_STATE_DELETE_ERROR
    raise StateError(
        unhandled_message,
        operation=operation,
        details={"plugin_name": plugin_name, "state": state},
    )
