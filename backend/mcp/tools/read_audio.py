"""SoAI - MCP tool for local plugin-backed audio reading [backend/mcp/tools/read_audio.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.files.extensions.media import AUDIO_EXTENSIONS
from core.media.speech_setup import SpeechTask
from core.media.transcription_contracts import SpeechTranscriptionOptions
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.argument_runtime import resolve_tool_request_context
from mcp.tools.argument_scalars import parse_bool_strict_default
from mcp.tools.error import MCPToolError, guarded_tool_call
from mcp.tools.files_access import (
    normalize_str,
    resolve_existing_file_source,
)
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.speech_setup_visibility import with_scoped_speech_setup

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_read_audio",)

_TOOL_NAME = "read_audio"
_OPERATION = "mcp.tools.read_audio"
_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"file_id", "file_path", "model", "language", "task", "include_word_timestamps"},
)


async def tool_read_audio(self: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    file_id = normalize_str(arguments.get("file_id"), field="file_id", required=False)
    file_path_arg = normalize_str(arguments.get("file_path"), field="file_path", required=False)
    file_path = await resolve_existing_file_source(
        self,
        file_id=file_id,
        document_id=None,
        file_path=file_path_arg,
        missing_message="Must provide one of: file_id or file_path",
    )
    _validate_audio_extension(file_path)
    selector = _extract_model_selector(arguments)
    options = SpeechTranscriptionOptions(
        task=_extract_task(arguments),
        language=_extract_language(arguments),
        include_word_timestamps=parse_bool_strict_default(
            arguments.get("include_word_timestamps"),
            field_name="include_word_timestamps",
            default=False,
        ),
    )
    result = await guarded_tool_call(
        _OPERATION,
        _TOOL_NAME,
        with_scoped_speech_setup(
            self,
            self.read_audio_gateway.read_audio(
                file_path=file_path,
                selector=selector,
                options=options,
                request_context=resolve_tool_request_context(self, tool_name=_TOOL_NAME),
            ),
        ),
    )
    if not isinstance(result, dict):
        raise MCPToolError(-32603, "read_audio returned an invalid result.")
    return result


def _validate_audio_extension(file_path: str) -> None:
    _, extension = os.path.splitext(file_path)
    normalized_extension = extension.lower().lstrip(".")
    if normalized_extension not in AUDIO_EXTENSIONS:
        supported_list = ", ".join(f".{item}" for item in sorted(AUDIO_EXTENSIONS))
        raise MCPToolError(
            -32602,
            f"Unsupported audio format: {extension}. Supported: {supported_list}",
        )


def _extract_model_selector(arguments: JSONDict) -> str | None:
    raw_value = arguments.get("model")
    if raw_value is None:
        return None
    if isinstance(raw_value, str) and (not raw_value.strip()):
        raise MCPToolError(-32602, "model must be a non-empty string when provided")
    return normalize_str(raw_value, field="model", required=False)


def _extract_language(arguments: JSONDict) -> str | None:
    return normalize_str(arguments.get("language"), field="language", required=False)


def _extract_task(arguments: JSONDict) -> SpeechTask:
    raw_value = arguments.get("task")
    if raw_value is None:
        return SpeechTask.TRANSCRIBE
    if isinstance(raw_value, str) and (not raw_value.strip()):
        raise MCPToolError(-32602, "task must be a non-empty string when provided")
    task_value = normalize_str(raw_value, field="task", required=False) or SpeechTask.TRANSCRIBE
    try:
        return SpeechTask(task_value)
    except ValueError as exception:
        valid_list = ", ".join(task.value for task in SpeechTask)
        raise MCPToolError(
            -32602, f"Invalid task: {task_value}. Valid: {valid_list}"
        ) from exception
