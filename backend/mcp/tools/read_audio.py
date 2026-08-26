"""SoAI - MCP tool for audio reading using Whisper [backend/mcp/tools/read_audio.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError, ValidationError
from core.files.extensions.media import AUDIO_EXTENSIONS
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.argument_scalars import parse_bool_strict_default
from mcp.tools.error import MCPToolError
from mcp.tools.files_access import (
    normalize_str,
    resolve_existing_file_source,
)
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_read_audio",)

_VALID_MODELS = frozenset({"tiny", "base", "small", "medium", "large", "large-v2", "large-v3"})
_VALID_TASKS = frozenset({"transcribe", "translate"})
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
    model_name = _extract_model_name(arguments)
    language = _extract_language(arguments)
    task = _extract_task(arguments)
    include_word_timestamps = parse_bool_strict_default(
        arguments.get("include_word_timestamps"),
        field_name="include_word_timestamps",
        default=False,
    )
    try:
        audio_result = await self.read_audio_gateway.read_audio(
            file_path=file_path,
            model_name=model_name,
            language=language,
            task=task,
            include_word_timestamps=include_word_timestamps,
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, exception.message) from exception
    except SoAIError as exception:
        raise MCPToolError(-32603, exception.message) from exception
    return audio_result


def _validate_audio_extension(file_path: str) -> None:
    _, extension = os.path.splitext(file_path)
    normalized_extension = extension.lower().lstrip(".")
    if normalized_extension not in AUDIO_EXTENSIONS:
        supported_list = ", ".join(f".{item}" for item in sorted(AUDIO_EXTENSIONS))
        raise MCPToolError(
            -32602,
            f"Unsupported audio format: {extension}. Supported: {supported_list}",
        )


def _extract_model_name(arguments: JSONDict) -> str:
    raw_value = arguments.get("model")
    if raw_value is None:
        return "base"
    if isinstance(raw_value, str) and (not raw_value.strip()):
        raise MCPToolError(-32602, "model must be a non-empty string when provided")
    model_value = normalize_str(raw_value, field="model", required=False) or "base"
    if model_value not in _VALID_MODELS:
        valid_list = ", ".join(sorted(_VALID_MODELS))
        raise MCPToolError(-32602, f"Invalid model: {model_value}. Valid: {valid_list}")
    return model_value


def _extract_language(arguments: JSONDict) -> str | None:
    return normalize_str(arguments.get("language"), field="language", required=False)


def _extract_task(arguments: JSONDict) -> str:
    raw_value = arguments.get("task")
    if raw_value is None:
        return "transcribe"
    if isinstance(raw_value, str) and (not raw_value.strip()):
        raise MCPToolError(-32602, "task must be a non-empty string when provided")
    task_value = normalize_str(raw_value, field="task", required=False) or "transcribe"
    if task_value not in _VALID_TASKS:
        valid_list = ", ".join(sorted(_VALID_TASKS))
        raise MCPToolError(-32602, f"Invalid task: {task_value}. Valid: {valid_list}")
    return task_value
