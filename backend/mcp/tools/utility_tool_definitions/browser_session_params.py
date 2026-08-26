"""SoAI - MCP utility tool definitions: shared browser session parameters [backend/mcp/tools/utility_tool_definitions/browser_session_params.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_enum_schema,
    nullable_non_empty_string_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_browser_action_input_schema",
    "build_browser_session_input_schema",
    "build_browser_session_param_properties",
)


def build_browser_session_param_properties() -> JSONDict:
    return {
        "profile": nullable_non_empty_string_schema(
            description="Browser profile name (must be configured under TOOLS.MCP.BROWSER.PROFILES).",
        ),
        "session_scope": nullable_enum_schema(
            ("conversation", "user"),
            description="Session ownership scope. conversation isolates sessions by conversation id; user shares across conversations for the same user.",
        ),
    }


def build_browser_session_input_schema(*, session_params: JSONDict) -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {**session_params},
    }


def build_browser_action_input_schema(
    *,
    actions: tuple[str, ...],
    session_params: JSONDict,
    extra_properties: JSONDict,
    action_description: str | None = None,
) -> JSONDict:
    action_schema: JSONDict = {
        "type": "string",
        "enum": list(actions),
        "minLength": 1,
    }
    if action_description is not None:
        action_schema["description"] = action_description
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action"],
        "properties": {
            "action": action_schema,
            **extra_properties,
            **session_params,
        },
    }
