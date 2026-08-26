"""SoAI - MCP utility tool: read_file [backend/mcp/tools/file_read_file.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.files.image_candidates import is_supported_image_candidate
from core.mcp.argument_validation import (
    require_no_unknown_keys,
    require_non_empty_string_value,
)
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError, build_invalid_params_error, get_arg
from mcp.tools.file_guard import record_file_read_with_signature
from mcp.tools.file_read_omission_payloads import build_oversize_omitted_payload
from mcp.tools.file_stable_snapshot import read_stable_file_snapshot
from mcp.tools.file_text_reading import (
    ReadFileTextOptions,
    read_text_file_for_tool,
    require_raw_mode_arguments,
)
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("tool_read_file",)

_DEFAULT_OFFSET: int = 1
_DEFAULT_LIMIT: int = 2000
_MAX_LIMIT: int = 20_000
_MAX_READ_FILE_BYTES: int = 4 * MIB_BYTES
_ALLOWED_KEYS: frozenset[str] = frozenset(
    ("file_path", "offset", "limit", "mode", "render", "indentation"),
)


def _require_only_allowed_keys(arguments: JSONDict, *, allowed: frozenset[str]) -> None:
    require_no_unknown_keys(
        arguments,
        allowed,
        build_error=build_invalid_params_error,
        message=lambda unknown_keys: f"Unknown argument(s) for read_file: {', '.join(unknown_keys)}. Supported keys: {', '.join(sorted(allowed))}.",
    )


def _normalize_mode(mode_value: JSONValue) -> str:
    if mode_value is None:
        return "slice"
    if not isinstance(mode_value, str):
        raise MCPToolError(-32602, "mode must be a string")
    normalized_mode = mode_value.strip().lower()
    if not normalized_mode:
        raise MCPToolError(-32602, "mode must be a non-empty string")
    if normalized_mode in {"slice", "indentation", "raw"}:
        return normalized_mode
    raise MCPToolError(
        -32602,
        f"Unknown mode: {normalized_mode}. Supported: slice, indentation, raw.",
    )


def _normalize_render(render_value: JSONValue) -> str:
    if render_value is None:
        return "raw"
    if not isinstance(render_value, str):
        raise MCPToolError(-32602, "render must be a string")
    normalized_render = render_value.strip().lower()
    if not normalized_render:
        raise MCPToolError(-32602, "render must be a non-empty string")
    if normalized_render in {"numbered", "raw"}:
        return normalized_render
    raise MCPToolError(
        -32602,
        f"Unknown render: {normalized_render}. Supported: numbered, raw.",
    )


async def tool_read_file(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    file_path = get_arg(arguments, "file_path")
    normalized_file_path = require_non_empty_string_value(
        file_path,
        build_error=build_invalid_params_error,
        type_message="file_path must be a non-empty string",
        empty_message="file_path must be a non-empty string",
    )
    _require_only_allowed_keys(arguments, allowed=_ALLOWED_KEYS)
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    files_state = utility_tools.runtime_sessions.get_or_create_workspace_state(owner_key)

    normalized_mode = _normalize_mode(arguments.get("mode", "slice"))
    if normalized_mode == "raw":
        require_raw_mode_arguments(arguments)
    normalized_render = _normalize_render(arguments.get("render"))

    offset = parse_int(
        arguments.get("offset"),
        default=_DEFAULT_OFFSET,
        min_value=1,
        max_value=10_000_000,
    )
    limit = parse_int(
        arguments.get("limit"),
        default=_DEFAULT_LIMIT,
        min_value=1,
        max_value=_MAX_LIMIT,
    )
    snapshot = await asyncio.to_thread(
        read_stable_file_snapshot,
        utility_tools,
        normalized_file_path,
        max_bytes=_MAX_READ_FILE_BYTES,
        description="file_path",
        sample_only_when_oversize=True,
    )
    if snapshot.exceeded_max_bytes:
        result = build_oversize_omitted_payload(
            path=snapshot.resolved_path,
            mode=normalized_mode,
            offset=offset,
            limit=limit,
            sample=snapshot.mime_sample,
            size_bytes=snapshot.source_size_bytes,
            max_size_bytes=_MAX_READ_FILE_BYTES,
        )
    else:
        result = await asyncio.to_thread(
            read_text_file_for_tool,
            snapshot.resolved_path,
            ReadFileTextOptions(
                mode=normalized_mode,
                render=normalized_render,
                offset=offset,
                limit=limit,
                indentation=arguments.get("indentation"),
            ),
            snapshot.data,
        )
    _add_read_image_hint(result, path=snapshot.resolved_path)
    record_file_read_with_signature(files_state, snapshot.resolved_path, snapshot.signature)
    return result


def _add_read_image_hint(result: JSONDict, *, path: str) -> None:
    if result.get("binary") is not True:
        return
    mime_type = result.get("mime_type")
    if not isinstance(mime_type, str):
        return
    if not is_supported_image_candidate(path=path, content_type=mime_type):
        return
    result["read_image_hint"] = (
        "use read_image for vision-native inspection; use read_document only for OCR/text extraction"
    )
    result["read_image_args"] = {"file_path": path}
