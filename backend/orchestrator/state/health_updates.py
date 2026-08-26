"""SoAI - Plugin state health detail updates [backend/orchestrator/state/health_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict

__all__ = ("apply_plugin_health_status_update",)


def apply_plugin_health_status_update(
    plugin_state: JSONDict,
    health_status: str,
) -> bool:
    details_value = plugin_state.get("details")
    current_details = details_value if isinstance(details_value, dict) else {}
    existing_health_status = current_details.get("health_status")
    if existing_health_status == health_status:
        return False
    details = dict(current_details)
    details["health_status"] = health_status
    plugin_state["details"] = details
    return True
