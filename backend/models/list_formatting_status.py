"""SoAI - Plugin availability and status message formatting for model lists [backend/models/list_formatting_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.state.health_status import (
    PLUGIN_HEALTH_OPEN,
    PLUGIN_HEALTH_QUARANTINED,
    PLUGIN_HEALTH_RECOVERING,
)
from core.state.provider_backed_availability import (
    PROVIDER_BACKED_IGNORED_PLUGIN_STATES,
)
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_ERROR,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_NOT_DETECTED,
)
from core.state.state_transition_sets import ALL_TRANSIENT_STATES, OPERATIONAL_ERROR_STATES
from core.validation.boolean_coercion import coerce_bool_with_default

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginState
    from core.types.json import JSONDict

__all__ = ("get_model_status_message",)


def get_model_status_message(
    model_data: JSONDict,
    plugin_state_info: ImmutablePluginState,
    orphaned: bool,
    no_backend: bool,
    provider_backed: bool = False,
) -> str:
    status = plugin_state_info.get("status", PLUGIN_STATE_NOT_DETECTED)
    details = plugin_state_info.get("details")
    health_status = details.get("health_status") if isinstance(details, Mapping) else None
    if orphaned:
        return f"Plugin '{model_data.get('plugin')}' is not installed or has been deleted."
    if status == ORCH_STATE_DISABLED:
        return (
            "Disabled (Backend not installed)"
            if no_backend
            else "Plugin is manually disabled by an administrator."
        )
    if not coerce_bool_with_default(model_data.get("is_enabled"), default=True, strict=True):
        return "Model is disabled."
    if model_data.get("status") != "active":
        return f"Model is marked as '{model_data.get('status')}' in the database."
    if not provider_backed and health_status == PLUGIN_HEALTH_OPEN:
        return (
            "Plugin is temporarily unavailable due to repeated failures (circuit breaker is open)."
        )
    if not provider_backed and health_status == PLUGIN_HEALTH_RECOVERING:
        return (
            "Plugin is recovering after repeated failures and has not passed its health probe yet."
        )
    if health_status == PLUGIN_HEALTH_QUARANTINED:
        return "Plugin has been quarantined due to persistent failures."
    if status == PLUGIN_STATE_INCOMPATIBLE:
        return "Plugin is incompatible with the current SoAI version."
    if provider_backed and status in PROVIDER_BACKED_IGNORED_PLUGIN_STATES:
        return ""
    if not provider_backed and status in [
        PLUGIN_STATE_NOT_DETECTED,
        PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    ]:
        return "Plugin backend is not installed."
    if not provider_backed and (status in OPERATIONAL_ERROR_STATES or status == ORCH_STATE_ERROR):
        return f"Plugin is in an error state: {status}."
    return f"Plugin is busy: {status}." if status in ALL_TRANSIENT_STATES else ""
