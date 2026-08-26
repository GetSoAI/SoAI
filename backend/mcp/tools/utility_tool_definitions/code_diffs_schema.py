"""SoAI - MCP code_diffs JSON schema helpers [backend/mcp/tools/utility_tool_definitions/code_diffs_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_code_diff_entry_schema",
    "build_code_diffs_schema",
)


def build_code_diff_entry_schema() -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "path": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["added", "updated", "deleted"],
            },
            "diff": {"type": "string"},
            "truncated": {"type": "boolean"},
        },
        "required": ["path", "operation", "diff", "truncated"],
    }


def build_code_diffs_schema() -> JSONDict:
    return {"type": "array", "items": build_code_diff_entry_schema()}
