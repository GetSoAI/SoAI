"""SoAI - MCP utility tool definition: text_stats [backend/mcp/tools/utility_tool_definitions/text_stats.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.protocol.icons import ICON_DOC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_text_stats_tool_definitions",)


def build_text_stats_tool_definitions() -> dict[str, JSONDict]:
    return {
        "text_stats": {
            "title": "Text Statistics",
            "description": "Analyze text and return statistics: character count, word count, token count, sentence count, reading time",
            "icons": [build_tool_icon_entry(ICON_DOC)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"text": {"type": "string", "description": "Text to analyze"}},
                "required": ["text"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "characters": {
                        "type": "integer",
                        "description": "Total character count",
                    },
                    "characters_no_spaces": {
                        "type": "integer",
                        "description": "Characters excluding spaces",
                    },
                    "words": {"type": "integer", "description": "Word count"},
                    "sentences": {"type": "integer", "description": "Sentence count"},
                    "paragraphs": {"type": "integer", "description": "Paragraph count"},
                    "lines": {"type": "integer", "description": "Line count"},
                    "tokens": {"type": "integer", "description": "Token count (cl100k_base)"},
                    "reading_time_minutes": {
                        "type": "number",
                        "description": "Estimated reading time in minutes (200 wpm)",
                    },
                    "speaking_time_minutes": {
                        "type": "number",
                        "description": "Estimated speaking time in minutes (150 wpm)",
                    },
                },
            },
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=False,
            ),
        },
    }
