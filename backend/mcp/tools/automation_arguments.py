"""SoAI - MCP automation tool argument keysets [backend/mcp/tools/automation_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.automation_constants import AUTOMATION_PAYLOAD_FIELDS

__all__ = (
    "allowed_automation_create_keys",
    "allowed_automation_get_run_keys",
    "allowed_automation_run_now_keys",
    "allowed_automation_update_keys",
    "allowed_automation_wait_run_keys",
)


def allowed_automation_create_keys() -> frozenset[str]:
    return frozenset(AUTOMATION_PAYLOAD_FIELDS)


def allowed_automation_update_keys() -> frozenset[str]:
    return frozenset(("automation_id", *AUTOMATION_PAYLOAD_FIELDS))


def allowed_automation_run_now_keys() -> frozenset[str]:
    return frozenset({"automation_id"})


def allowed_automation_get_run_keys() -> frozenset[str]:
    return frozenset({"run_id"})


def allowed_automation_wait_run_keys() -> frozenset[str]:
    return frozenset({"run_id", "timeout_ms"})
