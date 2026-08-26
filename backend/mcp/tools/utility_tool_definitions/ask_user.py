"""SoAI - MCP utility tool definition: ask_user [backend/mcp/tools/utility_tool_definitions/ask_user.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_CHAT

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_ask_user_tool_definitions",)


def build_ask_user_tool_definitions() -> dict[str, JSONDict]:
    option_schema: JSONDict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string", "description": "Short option label (max 256 chars)."},
            "description": {
                "type": "string",
                "description": "Short secondary text shown under the label (max 1024 chars).",
            },
        },
        "required": ["label", "description"],
    }
    question_schema: JSONDict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "id": {
                "type": "string",
                "description": "Optional stable question id. If omitted, SoAI generates 0, 1, 2...",
            },
            "header": {
                "type": "string",
                "description": "Optional short label shown above the question (max 256 chars).",
            },
            "question": {
                "type": "string",
                "description": "Question text shown to the user (max 4096 chars).",
            },
            "multi_select": {
                "type": "boolean",
                "description": "Allow multiple option selections for this question (default false).",
            },
            "is_secret": {
                "type": "boolean",
                "description": "Mask free-text input in the UI while still returning the plain answer to the tool call (default false).",
            },
            "options": {
                "type": "array",
                "description": "Optional list of 2-6 human-readable choices. Free-text Other/notes input is always available.",
                "items": option_schema,
            },
        },
        "required": ["question"],
    }
    answer_schema: JSONDict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "answers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Selected option labels in original order, followed by free-text input when provided.",
            },
        },
        "required": ["answers"],
    }
    return {
        "ask_user": {
            "title": "Ask User",
            "description": (
                "Present one to six questions to the user in the chat UI, pause execution, "
                "and wait for their response or cancellation. Prefer one to three questions "
                "and two to four choices when options are needed. Use is_secret only for "
                "non-credential confidential free-text."
            ),
            "icons": [build_tool_icon_entry(ICON_CHAT)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "questions": {
                        "type": "array",
                        "description": "Ordered list of one to six question objects.",
                        "items": question_schema,
                    },
                },
                "required": ["questions"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "answers": {
                        "type": "object",
                        "additionalProperties": answer_schema,
                    },
                },
                "required": ["answers"],
            },
            "annotations": build_tool_annotation_flags(),
        },
    }
