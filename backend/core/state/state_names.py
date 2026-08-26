"""SoAI - Canonical state string constants [backend/core/state/state_names.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    type PluginStateName = Literal[
        "NOT_DETECTED",
        "BACKEND_NOT_INSTALLED",
        "BACKEND_INSTALLING",
        "BACKEND_UPDATING",
        "STOPPED",
        "REMOVING_BACKEND",
        "DELETING",
        "INSTALL_ERROR",
        "LOAD_ERROR",
        "UPDATE_ERROR",
        "BACKEND_UNINSTALL_ERROR",
        "DELETE_ERROR",
        "PERSISTENT_READY",
        "ABSENT",
        "INCOMPATIBLE",
    ]
    type OrchestratorStateName = Literal[
        "UNKNOWN",
        "STOPPED",
        "STARTING",
        "LOADING",
        "IDLE",
        "READY_PENDING_DISPATCH",
        "READY",
        "READY_DIRTY",
        "PROCESSING",
        "STOPPING",
        "ERROR",
        "QUARANTINED",
        "DISABLED",
    ]
    type PluginRuntimeStateName = PluginStateName | OrchestratorStateName
else:
    PluginStateName = str
    OrchestratorStateName = str
    PluginRuntimeStateName = str

__all__ = ("resolve_plugin_runtime_state_name",)

PLUGIN_STATE_NOT_DETECTED: Final[PluginStateName] = "NOT_DETECTED"
PLUGIN_STATE_BACKEND_NOT_INSTALLED: Final[PluginStateName] = "BACKEND_NOT_INSTALLED"
PLUGIN_STATE_BACKEND_INSTALLING: Final[PluginStateName] = "BACKEND_INSTALLING"
PLUGIN_STATE_BACKEND_UPDATING: Final[PluginStateName] = "BACKEND_UPDATING"
PLUGIN_STATE_STOPPED: Final[PluginStateName] = "STOPPED"
PLUGIN_STATE_REMOVING_BACKEND: Final[PluginStateName] = "REMOVING_BACKEND"
PLUGIN_STATE_DELETING: Final[PluginStateName] = "DELETING"
PLUGIN_STATE_INSTALL_ERROR: Final[PluginStateName] = "INSTALL_ERROR"
PLUGIN_STATE_LOAD_ERROR: Final[PluginStateName] = "LOAD_ERROR"
PLUGIN_STATE_UPDATE_ERROR: Final[PluginStateName] = "UPDATE_ERROR"
PLUGIN_STATE_BACKEND_UNINSTALL_ERROR: Final[PluginStateName] = "BACKEND_UNINSTALL_ERROR"
PLUGIN_STATE_DELETE_ERROR: Final[PluginStateName] = "DELETE_ERROR"
PLUGIN_STATE_PERSISTENT_READY: Final[PluginStateName] = "PERSISTENT_READY"
PLUGIN_STATE_ABSENT: Final[PluginStateName] = "ABSENT"
PLUGIN_STATE_INCOMPATIBLE: Final[PluginStateName] = "INCOMPATIBLE"

ORCH_STATE_UNKNOWN: Final[OrchestratorStateName] = "UNKNOWN"
ORCH_STATE_STOPPED: Final[OrchestratorStateName] = "STOPPED"
ORCH_STATE_STARTING: Final[OrchestratorStateName] = "STARTING"
ORCH_STATE_LOADING: Final[OrchestratorStateName] = "LOADING"
ORCH_STATE_IDLE: Final[OrchestratorStateName] = "IDLE"
ORCH_STATE_READY_PENDING_DISPATCH: Final[OrchestratorStateName] = "READY_PENDING_DISPATCH"
ORCH_STATE_READY: Final[OrchestratorStateName] = "READY"
ORCH_STATE_READY_DIRTY: Final[OrchestratorStateName] = "READY_DIRTY"
ORCH_STATE_PROCESSING: Final[OrchestratorStateName] = "PROCESSING"
ORCH_STATE_STOPPING: Final[OrchestratorStateName] = "STOPPING"
ORCH_STATE_ERROR: Final[OrchestratorStateName] = "ERROR"
ORCH_STATE_QUARANTINED: Final[OrchestratorStateName] = "QUARANTINED"
ORCH_STATE_DISABLED: Final[OrchestratorStateName] = "DISABLED"

PLUGIN_STATE_NAMES: Final[tuple[PluginStateName, ...]] = (
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_BACKEND_INSTALLING,
    PLUGIN_STATE_BACKEND_UPDATING,
    PLUGIN_STATE_STOPPED,
    PLUGIN_STATE_REMOVING_BACKEND,
    PLUGIN_STATE_DELETING,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_UPDATE_ERROR,
    PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
    PLUGIN_STATE_DELETE_ERROR,
    PLUGIN_STATE_PERSISTENT_READY,
    PLUGIN_STATE_ABSENT,
    PLUGIN_STATE_INCOMPATIBLE,
)

ORCHESTRATOR_STATE_NAMES: Final[tuple[OrchestratorStateName, ...]] = (
    ORCH_STATE_UNKNOWN,
    ORCH_STATE_STOPPED,
    ORCH_STATE_STARTING,
    ORCH_STATE_LOADING,
    ORCH_STATE_IDLE,
    ORCH_STATE_READY_PENDING_DISPATCH,
    ORCH_STATE_READY,
    ORCH_STATE_READY_DIRTY,
    ORCH_STATE_PROCESSING,
    ORCH_STATE_STOPPING,
    ORCH_STATE_ERROR,
    ORCH_STATE_QUARANTINED,
    ORCH_STATE_DISABLED,
)

ORCHESTRATOR_STATE_NAMES_WITHOUT_UNKNOWN: Final[tuple[OrchestratorStateName, ...]] = (
    ORCH_STATE_STOPPED,
    ORCH_STATE_STARTING,
    ORCH_STATE_LOADING,
    ORCH_STATE_IDLE,
    ORCH_STATE_READY_PENDING_DISPATCH,
    ORCH_STATE_READY,
    ORCH_STATE_READY_DIRTY,
    ORCH_STATE_PROCESSING,
    ORCH_STATE_STOPPING,
    ORCH_STATE_ERROR,
    ORCH_STATE_QUARANTINED,
    ORCH_STATE_DISABLED,
)


def resolve_plugin_runtime_state_name(state_name: str | None) -> PluginRuntimeStateName | None:
    if not isinstance(state_name, str):
        return None
    candidate = state_name.strip().upper()
    if not candidate:
        return None
    match candidate:
        case "NOT_DETECTED":
            return PLUGIN_STATE_NOT_DETECTED
        case "BACKEND_NOT_INSTALLED":
            return PLUGIN_STATE_BACKEND_NOT_INSTALLED
        case "BACKEND_INSTALLING":
            return PLUGIN_STATE_BACKEND_INSTALLING
        case "BACKEND_UPDATING":
            return PLUGIN_STATE_BACKEND_UPDATING
        case "STOPPED":
            return PLUGIN_STATE_STOPPED
        case "REMOVING_BACKEND":
            return PLUGIN_STATE_REMOVING_BACKEND
        case "DELETING":
            return PLUGIN_STATE_DELETING
        case "INSTALL_ERROR":
            return PLUGIN_STATE_INSTALL_ERROR
        case "LOAD_ERROR":
            return PLUGIN_STATE_LOAD_ERROR
        case "UPDATE_ERROR":
            return PLUGIN_STATE_UPDATE_ERROR
        case "BACKEND_UNINSTALL_ERROR":
            return PLUGIN_STATE_BACKEND_UNINSTALL_ERROR
        case "DELETE_ERROR":
            return PLUGIN_STATE_DELETE_ERROR
        case "PERSISTENT_READY":
            return PLUGIN_STATE_PERSISTENT_READY
        case "ABSENT":
            return PLUGIN_STATE_ABSENT
        case "INCOMPATIBLE":
            return PLUGIN_STATE_INCOMPATIBLE
        case "UNKNOWN":
            return ORCH_STATE_UNKNOWN
        case "STARTING":
            return ORCH_STATE_STARTING
        case "LOADING":
            return ORCH_STATE_LOADING
        case "IDLE":
            return ORCH_STATE_IDLE
        case "READY_PENDING_DISPATCH":
            return ORCH_STATE_READY_PENDING_DISPATCH
        case "READY":
            return ORCH_STATE_READY
        case "READY_DIRTY":
            return ORCH_STATE_READY_DIRTY
        case "PROCESSING":
            return ORCH_STATE_PROCESSING
        case "STOPPING":
            return ORCH_STATE_STOPPING
        case "ERROR":
            return ORCH_STATE_ERROR
        case "QUARANTINED":
            return ORCH_STATE_QUARANTINED
        case "DISABLED":
            return ORCH_STATE_DISABLED
        case _:
            return None
