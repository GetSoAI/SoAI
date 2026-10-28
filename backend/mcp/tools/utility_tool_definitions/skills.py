"""SoAI - Internal conversation skill tool definitions [backend/mcp/tools/utility_tool_definitions/skills.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from core.skills.limits import MAX_ENTRIES, MAX_INVOCATION_ARGUMENT_CHARACTERS, MAX_PATH_BYTES
from mcp.tools.icons import ICON_SKILLS

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_skill_tool_definitions",)


def build_skill_tool_definitions() -> dict[str, JSONDict]:
    resource_inventory: JSONDict = {
        "type": "array",
        "maxItems": MAX_ENTRIES,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "path": {"type": "string"},
                "is_directory": {"type": "boolean"},
                "size_bytes": {"type": "integer", "minimum": 0},
                "digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            },
            "required": ["path", "is_directory", "size_bytes", "digest"],
        },
    }
    return {
        "skill_read": {
            "title": "Read Skill",
            "description": (
                "Skills give the assistant instructions for specific tasks. "
                "Load a skill's instructions or read its supporting files. "
                "Loading a skill does not grant permissions or run its files."
            ),
            "icons": [build_tool_icon_entry(ICON_SKILLS)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "skill_id": {
                        "type": "string",
                        "pattern": "^skill_[0-9a-f]{32}$",
                        "description": "The ID of a skill listed in this turn's skill context.",
                    },
                    "arguments": {
                        "type": "string",
                        "maxLength": MAX_INVOCATION_ARGUMENT_CHARACTERS,
                        "description": "Optional arguments for an activation. Omit when reading resources. Admitted human arguments take precedence and cannot be replaced.",
                    },
                    "source_relative": {
                        "type": "boolean",
                        "description": "With path, read an exact collection supporting path listed by the captured profile. Omit for ordinary package-relative reads; never use parent traversal.",
                    },
                    "path": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_PATH_BYTES,
                        "description": (
                            "Omit to load the skill's complete instructions for this turn. "
                            "After loading, provide an exact path within the skill package "
                            "to read a supporting file. Text is paged; binary files return "
                            "file information only."
                        ),
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 2147483647,
                        "default": 1,
                        "description": "First text line to read, starting at 1. Requires path.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 2000,
                        "default": 200,
                        "description": "Maximum text lines to read. Requires path.",
                    },
                },
                "required": ["skill_id"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "skill_id": {"type": "string"},
                    "skill_name": {"type": "string"},
                    "activated": {"type": "boolean"},
                    "source_relative": {"type": "boolean"},
                    "resources": resource_inventory,
                    "path": {"type": "string"},
                    "digest": {"type": "string"},
                    "size_bytes": {"type": "integer"},
                    "is_directory": {"type": "boolean"},
                    "binary": {"type": "boolean"},
                    "content_omitted": {"type": "boolean"},
                    "materialize_hint": {"type": "string"},
                    "mode": {"type": "string"},
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer"},
                    "total_lines": {"type": "integer"},
                    "returned_lines": {"type": "integer"},
                    "start_line": {"type": ["integer", "null"]},
                    "end_line": {"type": ["integer", "null"]},
                    "next_offset": {"type": ["integer", "null"]},
                    "truncated": {"type": "boolean"},
                    "truncation_reason": {"type": ["string", "null"]},
                    "content_truncated": {"type": "boolean"},
                    "serialized_response_chars": {"type": "integer"},
                    "max_serialized_response_chars": {"type": ["integer", "null"]},
                    "content": {"type": "string"},
                },
                "required": ["skill_id"],
            },
            "annotations": build_tool_annotation_flags(
                read_only=True, destructive=False, idempotent=True, open_world=False
            ),
        },
        "skill_materialize": {
            "title": "Materialize Skill",
            "description": "Copy an active skill's complete files into a new private directory in the conversation workspace. Requires execute mode and the selected write tool's approval. Does not run files or install dependencies. Repeated calls for the same admitted execution return the original durable result; changed or missing output is never overwritten or recreated.",
            "icons": [build_tool_icon_entry(ICON_SKILLS)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"skill_id": {"type": "string", "pattern": "^skill_[0-9a-f]{32}$"}},
                "required": ["skill_id"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "skill_id": {"type": "string"},
                    "skill_name": {"type": "string"},
                    "task_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": [
                            "pending",
                            "completed",
                            "failed",
                            "cancelled",
                            "conflict",
                            "recovery_required",
                        ],
                    },
                    "materialized": {"type": ["boolean", "null"]},
                    "path": {"type": "string"},
                    "source_root": {"type": "string"},
                    "manifest_path": {"type": "string"},
                    "layout_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "resources": resource_inventory,
                    "details": {"type": ["object", "null"]},
                },
                "required": ["skill_id", "task_id", "status", "materialized"],
            },
            "annotations": build_tool_annotation_flags(
                read_only=False, destructive=True, idempotent=True, open_world=False
            ),
        },
    }
