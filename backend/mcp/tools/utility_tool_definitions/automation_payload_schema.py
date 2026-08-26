"""SoAI - Automation MCP payload schema builders [backend/mcp/tools/utility_tool_definitions/automation_payload_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.automation_constants import (
    AUTOMATION_HARD_MAX_RUN_MINUTES,
    AUTOMATION_HARD_MAX_TURN_CHARS,
    AUTOMATION_HARD_MAX_TURNS,
    AUTOMATION_RECURRENCE_VALUES,
)
from core.types.json import JSONDict

__all__ = (
    "build_automation_create_payload_schema",
    "build_automation_update_payload_schema",
    "schema_properties",
    "schema_required",
)


def schema_properties(schema: JSONDict) -> JSONDict:
    properties = schema.get("properties")
    if isinstance(properties, dict):
        return dict(properties)
    return {}


def schema_required(schema: JSONDict) -> list[str]:
    required = schema.get("required")
    if not isinstance(required, list):
        return []
    return [field for field in required if isinstance(field, str)]


def build_automation_create_payload_schema() -> JSONDict:
    start_local_schema: JSONDict = {
        "type": "string",
        "description": "Local start time in the selected timezone. Format: YYYY-MM-DDTHH:mm (24-hour).",
        "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}$",
    }
    recurrence_schema: JSONDict = {
        "type": "string",
        "description": "Recurrence schedule. Cron expressions are not supported; use a recurrence enum plus start_local.",
        "enum": list(AUTOMATION_RECURRENCE_VALUES),
    }
    turns_schema: JSONDict = {
        "type": "array",
        "description": "Ordered automation turns as plain text instructions (the automation agent executes these turns).",
        "minItems": 1,
        "items": {"type": "string"},
    }
    limits_schema: dict[str, JSONDict] = {
        "max_turns": {
            "type": ["integer", "null"],
            "description": "Maximum number of turns allowed in the automation.",
            "minimum": 1,
            "maximum": AUTOMATION_HARD_MAX_TURNS,
        },
        "max_turn_chars": {
            "type": ["integer", "null"],
            "description": "Maximum number of characters allowed in each turn.",
            "minimum": 1,
            "maximum": AUTOMATION_HARD_MAX_TURN_CHARS,
        },
        "max_run_minutes": {
            "type": ["integer", "null"],
            "description": "Maximum runtime for a single automation run in minutes.",
            "minimum": 1,
            "maximum": AUTOMATION_HARD_MAX_RUN_MINUTES,
        },
    }
    agent_schema: JSONDict = {
        "type": ["object", "null"],
        "description": "Agent settings. Automation runs support execute mode only.",
        "additionalProperties": True,
        "properties": {
            "mode": {"type": "string", "enum": ["execute"]},
        },
    }
    model_settings_schema: JSONDict = {
        "description": (
            "OpenAI-style model settings for automation runs. "
            "Automation runs use execute agent mode. "
            "To enable tools for automation runs, set mcp.tools_enabled=true."
        ),
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "model": {"type": "string", "description": "Model id for the automation runs."},
            "agent": agent_schema,
            "mcp": {
                "type": ["object", "null"],
                "description": "MCP tool configuration for execute-mode automation runs.",
                "additionalProperties": True,
                "properties": {
                    "tools_enabled": {
                        "type": ["boolean", "null"],
                        "description": "Whether the automation agent can use tools.",
                    },
                },
            },
        },
        "required": ["model"],
    }
    return {
        "type": "object",
        "description": (
            "Automation definition payload. Scheduling uses timezone + start_local + recurrence "
            "(no cron/schedule/execution objects)."
        ),
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "description": "Automation title."},
            "enabled": {"type": "boolean", "description": "Whether the automation is enabled."},
            "color": {"type": ["string", "null"], "description": "Optional UI color."},
            "timezone": {
                "type": "string",
                "description": "IANA timezone name (e.g., UTC, America/New_York).",
            },
            "start_local": start_local_schema,
            "recurrence": recurrence_schema,
            "turns": turns_schema,
            **limits_schema,
            "interactive_tool_approval": {
                "type": "boolean",
                "description": "Whether to require interactive approval for tools during automation runs.",
            },
            "model_settings": model_settings_schema,
        },
        "required": [
            "title",
            "enabled",
            "timezone",
            "start_local",
            "recurrence",
            "turns",
            "interactive_tool_approval",
            "model_settings",
        ],
    }


def build_automation_update_payload_schema() -> JSONDict:
    create_payload_schema = build_automation_create_payload_schema()
    return {
        "type": "object",
        "description": "Partial automation update payload. Omit fields you do not want to change.",
        "additionalProperties": False,
        "properties": schema_properties(create_payload_schema),
    }
