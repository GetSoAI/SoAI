"""SoAI - Plugin health and availability resolution [backend/core/state/plugin_health_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.state.provider_backed_availability import (
    get_provider_aware_unavailable_plugin_states,
    is_provider_aware_health_available,
)
from core.types.json import JSONValue

__all__ = ("plugin_state_is_available",)


def plugin_state_is_available(
    plugin_state_info: Mapping[str, JSONValue],
    *,
    provider_backed: bool,
) -> bool:
    details = plugin_state_info.get("details")
    health_value = details.get("health_status") if isinstance(details, Mapping) else None
    health_status = health_value if isinstance(health_value, str) else None
    status_value = plugin_state_info.get("status")
    status = status_value if isinstance(status_value, str) else None
    unavailable_states = get_provider_aware_unavailable_plugin_states(provider_backed)
    if status is not None and status in unavailable_states:
        return False
    return is_provider_aware_health_available(health_status, provider_backed=provider_backed)
