"""SoAI - MCP utility tool definition: apply_patch [backend/mcp/tools/utility_tool_definitions/apply_patch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_PATCH
from mcp.tools.utility_tool_definitions.code_diffs_schema import build_code_diffs_schema

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_apply_patch_tool_definitions",)


def build_apply_patch_tool_definitions() -> dict[str, JSONDict]:
    return {
        "apply_patch": {
            "title": "Apply Patch",
            "description": (
                "Apply a structured patch to files under workspace_path. "
                "The patch must start with '*** Begin Patch' and end with '*** End Patch'. "
                "If the patch appears to be line-number prefixed (e.g., '1: *** Begin Patch'), prefixes are stripped. "
                "When the read-before-write file guard is enabled, edits to existing files require "
                "a prior read_file for text targets or read_image for image targets. "
                "Supported directives: '*** Add File: <path>' (content lines prefixed with +), "
                "'*** Delete File: <path>', "
                "'*** Update File: <path>' (unified diff hunks with @@, space/+/- prefixed lines). "
                "Update File supports '*** Move to: <path>' for renames."
            ),
            "icons": [build_tool_icon_entry(ICON_PATCH)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "Patch text starting with '*** Begin Patch' and ending with '*** End Patch'.",
                    },
                },
                "required": ["input"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "added": {"type": "array", "items": {"type": "string"}},
                    "updated": {"type": "array", "items": {"type": "string"}},
                    "deleted": {"type": "array", "items": {"type": "string"}},
                    "moved": {"type": "array", "items": {"type": "object"}},
                    "code_diffs": build_code_diffs_schema(),
                },
            },
            "annotations": build_tool_annotation_flags(destructive=True),
        },
    }
