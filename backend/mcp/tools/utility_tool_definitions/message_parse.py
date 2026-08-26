"""SoAI - MCP utility tool definition: message_parse [backend/mcp/tools/utility_tool_definitions/message_parse.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_MESSAGING
from mcp.tools.utility_tool_definitions.file_source_schema import (
    build_file_source_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_message_parse_tool_definitions",)


def build_message_parse_tool_definitions() -> dict[str, JSONDict]:
    return {
        "message_parse": {
            "title": "Messaging Export Parser",
            "description": "Parse chat exports from messaging platforms: WhatsApp, Telegram, Discord, Signal, Facebook Messenger, MSN Messenger. Supports .txt, .json, .xml, .csv, .html, and .zip files. Provide file_id (from /v1/files upload), document_id (RAG document), or file_path under workspace_path.",
            "icons": [build_tool_icon_entry(ICON_MESSAGING)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **build_file_source_properties(
                        file_path_description="Path to the messaging export file under workspace_path.",
                        include_url=False,
                        url_description="",
                    ),
                    "platform": {
                        "type": "string",
                        "description": "Platform hint (optional, auto-detected if not specified)",
                        "enum": [
                            "whatsapp",
                            "telegram",
                            "discord",
                            "signal",
                            "facebook",
                            "msn",
                            "auto",
                        ],
                    },
                    "max_messages": {
                        "type": "integer",
                        "description": "Maximum number of messages to return (default: all)",
                    },
                },
                "required": [],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Detected messaging platform",
                    },
                    "chat_name": {
                        "type": "string",
                        "description": "Name of the chat/conversation",
                    },
                    "participants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of participants in the conversation",
                    },
                    "message_count": {
                        "type": "integer",
                        "description": "Total number of messages parsed",
                    },
                    "content": {
                        "type": "string",
                        "description": "Formatted conversation content",
                    },
                    "media_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of referenced media files (for ZIP exports)",
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
