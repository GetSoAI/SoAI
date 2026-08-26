"""SoAI - MCP utility tool definitions: subagent_* [backend/mcp/tools/utility_tool_definitions/subagents.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import (
    SUBAGENT_ACKNOWLEDGEMENT_STATUSES,
    SUBAGENT_PERSISTED_STATUSES,
)
from core.agent.subagent_serialization import (
    build_subagent_accepted_execution_json_schema,
    build_subagent_snapshot_json_schema,
)
from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_MODEL

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_subagent_tool_definitions",)


def build_subagent_tool_definitions() -> dict[str, JSONDict]:
    icon = [build_tool_icon_entry(ICON_MODEL)]
    subagent_snapshot_schema = build_subagent_snapshot_json_schema(
        statuses=SUBAGENT_PERSISTED_STATUSES,
        modes=("plan", "execute"),
    )
    return {
        "subagent_spawn": {
            "title": "Subagent Spawn",
            "description": (
                "Spawn a background subagent for the current conversation turn. "
                "Omit tools to use the default subagent tool set, "
                "pass an empty array for text-only execution, "
                "or pass tool names to restrict the subagent to those tools."
            ),
            "icons": icon,
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "task": {"type": "string", "description": "Primary task for the subagent."},
                    "context": {
                        "type": ["string", "null"],
                        "description": "Optional extra context or constraints for the subagent.",
                    },
                    "mode": {
                        "type": ["string", "null"],
                        "enum": ["plan", "execute", None],
                        "description": (
                            "Subagent mode. Defaults to the current agent mode when omitted."
                        ),
                    },
                    "display_name": {
                        "type": ["string", "null"],
                        "description": "Optional label for UI display.",
                    },
                    "model": {
                        "type": ["string", "null"],
                        "description": "Optional model id override for the subagent.",
                    },
                    "workspace_path": {
                        "type": ["string", "null"],
                        "description": "Optional workspace path for file and shell tools.",
                    },
                    "max_iterations": {
                        "type": ["integer", "null"],
                        "description": (
                            "Optional maximum iteration cap for the subagent. "
                            "When omitted, defaults to the SoAI product default."
                        ),
                    },
                    "tools": {
                        "type": ["array", "null"],
                        "description": (
                            "Optional tool allowlist. Omit to use the default subagent tool set, "
                            "pass an empty array for text-only execution, "
                            "or pass tool names to restrict the subagent to those tools."
                        ),
                        "items": {"type": "string"},
                    },
                },
                "required": ["task"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "subagent": build_subagent_accepted_execution_json_schema(
                        accepted_statuses=SUBAGENT_ACKNOWLEDGEMENT_STATUSES,
                        modes=("plan", "execute"),
                    ),
                },
                "required": ["subagent"],
            },
            "annotations": build_tool_annotation_flags(),
        },
        "subagent_observe": {
            "title": "Subagent Observe",
            "description": (
                "Read a current-turn subagent snapshot. mode=current returns immediately; "
                "mode=terminal waits for completion, cancellation, error, or abandonment."
            ),
            "icons": icon,
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "subagent_id": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["current", "terminal"],
                        "description": "Return now or wait for a terminal state.",
                    },
                    "timeout_ms": {
                        "type": ["integer", "null"],
                        "minimum": 1,
                        "description": (
                            "Terminal mode only. Omit for the configured default, use null "
                            "for no timeout, or provide positive milliseconds."
                        ),
                    },
                },
                "required": ["subagent_id", "mode"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "subagent": subagent_snapshot_schema,
                    "timed_out": {"type": "boolean"},
                },
                "required": ["subagent", "timed_out"],
            },
            "annotations": build_tool_annotation_flags(read_only=True, idempotent=True),
        },
        "subagent_cancel": {
            "title": "Subagent Cancel",
            "description": (
                "Cancel a running subagent. Cancellation is cooperative/asynchronous and "
                "may not stop in-flight work immediately."
            ),
            "icons": icon,
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"subagent_id": {"type": "string"}},
                "required": ["subagent_id"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"cancelled": {"type": "boolean"}},
                "required": ["cancelled"],
            },
            "annotations": build_tool_annotation_flags(),
        },
    }
