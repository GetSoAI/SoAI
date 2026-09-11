"""SoAI - State metadata definitions for orchestrator and plugin states [backend/core/state/state_definitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_ERROR,
    ORCH_STATE_IDLE,
    ORCH_STATE_LOADING,
    ORCH_STATE_PROCESSING,
    ORCH_STATE_QUARANTINED,
    ORCH_STATE_READY,
    ORCH_STATE_READY_DIRTY,
    ORCH_STATE_READY_PENDING_DISPATCH,
    ORCH_STATE_STARTING,
    ORCH_STATE_STOPPED,
    ORCH_STATE_STOPPING,
    ORCH_STATE_UNKNOWN,
    PLUGIN_STATE_ABSENT,
    PLUGIN_STATE_BACKEND_INSTALLING,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
    PLUGIN_STATE_BACKEND_UPDATING,
    PLUGIN_STATE_DELETE_ERROR,
    PLUGIN_STATE_DELETING,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_PERSISTENT_READY,
    PLUGIN_STATE_REMOVING_BACKEND,
    PLUGIN_STATE_STOPPED,
    PLUGIN_STATE_UPDATE_ERROR,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("build_state_definitions",)

STATE_DEFAULT_STATUS = ORCH_STATE_UNKNOWN

STATE_ALLOWED_COLORS: tuple[str, ...] = (
    "blue",
    "green",
    "grey",
    "orange",
    "persistentgreen",
    "red",
)

STATE_DEFINITION_ENTRIES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (ORCH_STATE_UNKNOWN, "grey", "Status unknown", "system", ("unknown",)),
    (ORCH_STATE_STOPPED, "grey", "Stopped", "shared", ("inactive",)),
    (ORCH_STATE_STARTING, "blue", "Starting", "orchestrator", ("transition",)),
    (ORCH_STATE_LOADING, "blue", "Loading", "orchestrator", ("transition",)),
    (ORCH_STATE_IDLE, "green", "Idle", "orchestrator", ("active",)),
    (
        ORCH_STATE_READY_PENDING_DISPATCH,
        "blue",
        "Ready (pending dispatch)",
        "orchestrator",
        ("transition",),
    ),
    (ORCH_STATE_READY, "green", "Ready", "orchestrator", ("active",)),
    (ORCH_STATE_READY_DIRTY, "green", "Ready (modified)", "orchestrator", ("active",)),
    (ORCH_STATE_PROCESSING, "orange", "Processing", "orchestrator", ("active",)),
    (ORCH_STATE_STOPPING, "blue", "Stopping", "orchestrator", ("transition",)),
    (ORCH_STATE_ERROR, "red", "Error", "system", ("error",)),
    (ORCH_STATE_QUARANTINED, "red", "Quarantined", "system", ("error",)),
    (ORCH_STATE_DISABLED, "grey", "Disabled", "shared", ("inactive",)),
    (PLUGIN_STATE_NOT_DETECTED, "grey", "Not detected", "plugin_manager", ("inactive",)),
    (
        PLUGIN_STATE_BACKEND_NOT_INSTALLED,
        "grey",
        "Backend not installed",
        "plugin_manager",
        ("inactive",),
    ),
    (
        PLUGIN_STATE_BACKEND_INSTALLING,
        "orange",
        "Backend installing",
        "plugin_manager",
        ("transition",),
    ),
    (
        PLUGIN_STATE_BACKEND_UPDATING,
        "blue",
        "Backend updating",
        "plugin_manager",
        ("transition",),
    ),
    (PLUGIN_STATE_STOPPED, "grey", "Stopped", "shared", ("inactive",)),
    (
        PLUGIN_STATE_REMOVING_BACKEND,
        "blue",
        "Removing backend",
        "plugin_manager",
        ("transition",),
    ),
    (PLUGIN_STATE_DELETING, "blue", "Deleting", "plugin_manager", ("transition",)),
    (PLUGIN_STATE_INSTALL_ERROR, "red", "Install error", "plugin_manager", ("error",)),
    (PLUGIN_STATE_LOAD_ERROR, "red", "Load error", "plugin_manager", ("error",)),
    (PLUGIN_STATE_UPDATE_ERROR, "red", "Update error", "plugin_manager", ("error",)),
    (
        PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
        "red",
        "Backend uninstall error",
        "plugin_manager",
        ("error",),
    ),
    (PLUGIN_STATE_DELETE_ERROR, "red", "Delete error", "plugin_manager", ("error",)),
    (PLUGIN_STATE_PERSISTENT_READY, "persistentgreen", "Persistent", "plugin_manager", ("active",)),
    (PLUGIN_STATE_ABSENT, "grey", "Absent", "plugin_manager", ("inactive",)),
    (PLUGIN_STATE_INCOMPATIBLE, "red", "Incompatible", "plugin_manager", ("error",)),
)


def build_state_definitions() -> Mapping[str, Mapping[str, JSONValue]]:
    return MappingProxyType(
        {
            state_name: MappingProxyType(
                {
                    "name": state_name,
                    "color": color,
                    "description": description,
                    "group": group,
                    "tags": tags,
                },
            )
            for state_name, color, description, group, tags in STATE_DEFINITION_ENTRIES
        },
    )
