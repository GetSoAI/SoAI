"""SoAI - Plugin backend lifecycle runtime-state validation [backend/plugins/actions/backend_lifecycle_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.state.state_names import (
    PluginRuntimeStateName,
    resolve_plugin_runtime_state_name,
)

__all__ = ("require_runtime_state",)


def require_runtime_state(
    state_name: str,
    *,
    operation: str,
    plugin_name: str,
    trace_id: str,
) -> PluginRuntimeStateName:
    resolved = resolve_plugin_runtime_state_name(state_name)
    if resolved is None:
        raise StateError(
            "Invalid persisted plugin runtime state.",
            operation=operation,
            details={"plugin_name": plugin_name, "status": state_name, "trace_id": trace_id},
        )
    return resolved
