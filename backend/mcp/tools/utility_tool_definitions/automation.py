"""SoAI - MCP utility tool definitions: automation_* [backend/mcp/tools/utility_tool_definitions/automation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_run_serialization import (
    build_automation_run_snapshot_json_schema,
)
from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_AUTOMATION
from mcp.tools.utility_tool_definitions.automation_payload_schema import (
    build_automation_create_payload_schema,
    build_automation_update_payload_schema,
    schema_properties,
    schema_required,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_automation_tool_definitions",)


def build_automation_tool_definitions() -> dict[str, JSONDict]:
    create_payload_schema = build_automation_create_payload_schema()
    update_payload_schema = build_automation_update_payload_schema()
    return {
        "automation_create": {
            "title": "Automation Create",
            "description": (
                "Create an automation for the authenticated user. The payload must use the "
                "SoAI automation contract (timezone/start_local/recurrence/turns)."
            ),
            "icons": [build_tool_icon_entry(ICON_AUTOMATION)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": schema_properties(create_payload_schema),
                "required": schema_required(create_payload_schema),
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"automation": {"type": "object"}},
                "required": ["automation"],
            },
            "annotations": build_tool_annotation_flags(),
        },
        "automation_update": {
            "title": "Automation Update",
            "description": "Update an existing automation for the authenticated user.",
            "icons": [build_tool_icon_entry(ICON_AUTOMATION)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "automation_id": {"type": "string"},
                    **schema_properties(update_payload_schema),
                },
                "required": ["automation_id"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"automation": {"type": "object"}},
                "required": ["automation"],
            },
            "annotations": build_tool_annotation_flags(),
        },
        "automation_run_enqueue": {
            "title": "Automation Run Now",
            "description": "Enqueue an immediate automation run for the authenticated user.",
            "icons": [build_tool_icon_entry(ICON_AUTOMATION)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"automation_id": {"type": "string"}},
                "required": ["automation_id"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"run": build_automation_run_snapshot_json_schema(nullable=False)},
                "required": ["run"],
            },
            "annotations": build_tool_annotation_flags(),
        },
        "automation_run_get": {
            "title": "Automation Get Run",
            "description": "Fetch an automation run record for the authenticated user.",
            "icons": [build_tool_icon_entry(ICON_AUTOMATION)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"run": build_automation_run_snapshot_json_schema(nullable=True)},
                "required": ["run"],
            },
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
        "automation_run_wait": {
            "title": "Automation Wait Run",
            "description": "Wait for an automation run to reach a terminal state and return its record.",
            "icons": [build_tool_icon_entry(ICON_AUTOMATION)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "run_id": {"type": "string"},
                    "timeout_ms": {
                        "type": ["integer", "null"],
                        "description": (
                            "Maximum wait time in milliseconds; use 0 to return the current snapshot immediately. "
                            "When omitted, defaults to TOOLS.MCP.AUTOMATION.RUN_WAIT_TIMEOUT_MS (default 60000). "
                            "Use null for no timeout."
                        ),
                    },
                },
                "required": ["run_id"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"run": build_automation_run_snapshot_json_schema(nullable=True)},
                "required": ["run"],
            },
            "annotations": build_tool_annotation_flags(),
        },
    }
