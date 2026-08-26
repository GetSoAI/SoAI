"""SoAI - MCP utility tool definitions: browser_eval [backend/mcp/tools/utility_tool_definitions/browser_eval.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_EVAL
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    non_empty_string_schema,
    nullable_integer_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_eval_tool_definitions",)


def build_browser_eval_tool_definitions() -> dict[str, JSONDict]:
    icons = [build_tool_icon_entry(ICON_BROWSER_EVAL)]
    session_params = build_browser_session_param_properties()
    return {
        "browser_eval": {
            "title": "Browser Eval",
            "description": "Evaluate JavaScript in the active page (must be enabled via TOOLS.MCP.BROWSER.JS_EVAL_ENABLED).",
            "icons": icons,
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["script"],
                "properties": {
                    "script": non_empty_string_schema(
                        description="JavaScript function body. Use `return` to return a value. The script runs as `async function(arg) { <script> }` — `arg` holds the optional argument. Example: `return document.title` or `const x = window.scrollY; return x;`",
                    ),
                    "arg": {
                        "type": ["object", "array", "string", "number", "boolean", "null"],
                        "description": "Optional JSON-serializable argument passed to the script.",
                    },
                    "timeout_ms": nullable_integer_schema(
                        minimum=1000,
                        maximum=300000,
                        description="Evaluation timeout in milliseconds.",
                    ),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "evaluated": {"type": "boolean"},
                    "result": {"type": ["object", "array", "string", "number", "boolean", "null"]},
                    "result_type": {"type": "string"},
                    "downloads_dir": {"type": "string"},
                    "downloads": {"type": "array"},
                },
            },
            "annotations": build_tool_annotation_flags(
                read_only=False,
                destructive=False,
                idempotent=False,
                open_world=True,
            ),
        },
    }
