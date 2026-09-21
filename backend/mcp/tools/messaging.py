"""SoAI - MCP tool for parsing messaging platform exports [backend/mcp/tools/messaging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.types import ParseExecutionContext
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from core.users.ocr_preferences import resolve_user_ocr_language
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.error import MCPToolError
from mcp.tools.files_access import (
    normalize_str,
    resolve_existing_file_source,
)
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_message_parse",)

_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"file_id", "document_id", "file_path", "platform", "max_messages"},
)


async def tool_message_parse(self: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    file_id = normalize_str(arguments.get("file_id"), field="file_id", required=False)
    document_id = normalize_str(arguments.get("document_id"), field="document_id", required=False)
    file_path_arg = normalize_str(arguments.get("file_path"), field="file_path", required=False)
    file_path = await resolve_existing_file_source(
        self,
        file_id=file_id,
        document_id=document_id,
        file_path=file_path_arg,
        missing_message="Must provide one of: file_id, document_id, or file_path",
    )
    platform_hint_raw = arguments.get("platform")
    if platform_hint_raw is None:
        platform_hint = "auto"
    else:
        platform_hint_value = normalize_str(platform_hint_raw, field="platform", required=False)
        platform_hint = platform_hint_value or "auto"
    max_messages_raw = arguments.get("max_messages")
    max_messages: int | None = None
    if max_messages_raw is not None:
        if isinstance(max_messages_raw, bool) or not isinstance(max_messages_raw, int | float):
            raise MCPToolError(
                -32602,
                f"max_messages must be a number, got {type(max_messages_raw).__name__}",
            )
        max_messages = int(max_messages_raw)
        if max_messages <= 0:
            max_messages = None
    parsers = self.messaging_parser_registry_factory()
    if platform_hint == "auto":
        platform = self.messaging_platform_detector(file_path)
        if platform is None:
            raise MCPToolError(
                -32602,
                f"Could not detect messaging platform for file: {file_path}",
            )
    else:
        platform = platform_hint
    parser = parsers.get(platform)
    if parser is None:
        raise MCPToolError(
            -32602,
            f"Unknown platform: {platform}. Valid: {', '.join(parsers.keys())}",
        )
    ocr_language = await resolve_user_ocr_language(
        self.database_users, self.runtime_sessions.current_user_id()
    )
    try:
        result = await parser.parse(
            ParseExecutionContext(
                source_path=file_path,
                ocr_language=ocr_language,
                cancellation_token=None,
                progress_callback=None,
                display_name=None,
                extraction_deadline=time.monotonic() + INTERACTIVE_TIMEOUT_SEC,
            ),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        raise MCPToolError(-32603, f"Failed to parse messaging file: {exception}") from exception
    content = result.content
    if max_messages and max_messages > 0:
        content = _truncate_messages(content, max_messages, result.metadata)
    metadata = result.metadata or {}
    platform_value = metadata.get("platform")
    platform_name = platform_value if isinstance(platform_value, str) else platform
    title_value = metadata.get("title")
    chat_name_value = title_value if isinstance(title_value, str) else metadata.get("chat_name")
    chat_name = chat_name_value if isinstance(chat_name_value, str) else ""
    participants_value = metadata.get("participants")
    participants = (
        [item for item in participants_value if isinstance(item, str)]
        if isinstance(participants_value, list)
        else []
    )
    message_count_value = metadata.get("message_count")
    message_count = (
        int(message_count_value)
        if isinstance(message_count_value, int | float | str)
        and not isinstance(message_count_value, bool)
        else 0
    )
    media_files_value = metadata.get("media_files")
    media_files = (
        [item for item in media_files_value if isinstance(item, str)]
        if isinstance(media_files_value, list)
        else []
    )
    return {
        "platform": platform_name,
        "chat_name": chat_name,
        "participants": participants,
        "message_count": message_count,
        "content": content,
        "media_files": media_files,
    }


def _truncate_messages(content: str, max_messages: int, metadata: JSONDict | None) -> str:
    header_end = content.find("---\n")
    if header_end == -1:
        return content
    header = content[: header_end + 4]
    message_lines = content[header_end + 4 :].split("\n")
    message_count = 0
    truncated_lines: list[str] = []
    for line in message_lines:
        if line.startswith("[") and "**" in line:
            message_count += 1
            if message_count > max_messages:
                total_count_value = (metadata or {}).get("message_count", 0)
                total_count = (
                    int(total_count_value)
                    if isinstance(total_count_value, int | float)
                    and not isinstance(total_count_value, bool)
                    else 0
                )
                truncated_lines.append(f"\n... ({total_count - max_messages} more messages)")
                break
        truncated_lines.append(line)
    return header + "\n".join(truncated_lines)
