"""SoAI - MCP utility tool: read_image [backend/mcp/tools/read_image.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError
from core.files.image_candidates import is_supported_image_candidate
from core.files.inline_image_preparation import prepare_inline_image_for_prompt_relay
from core.mcp.argument_validation import (
    require_no_unknown_keys,
    require_non_empty_string_value,
)
from mcp.tools.error import MCPToolError, build_invalid_params_error, get_arg
from mcp.tools.file_guard import record_file_read_with_signature
from mcp.tools.file_stable_snapshot import read_stable_file_snapshot
from mcp.tools.read_image_config import resolve_read_image_config

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_read_image",)

_ALLOWED_KEYS: frozenset[str] = frozenset(("file_path",))


def _require_only_allowed_keys(arguments: JSONDict) -> None:
    require_no_unknown_keys(
        arguments,
        _ALLOWED_KEYS,
        build_error=build_invalid_params_error,
        message=lambda unknown_keys: f"Unknown argument(s) for read_image: {', '.join(unknown_keys)}. Supported keys: file_path.",
    )


async def tool_read_image(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    _require_only_allowed_keys(arguments)
    normalized_file_path = require_non_empty_string_value(
        get_arg(arguments, "file_path"),
        build_error=build_invalid_params_error,
        type_message="file_path must be a non-empty string",
        empty_message="file_path must be a non-empty string",
    )
    try:
        limits = resolve_read_image_config(utility_tools.config)
    except ConfigurationError as exception:
        raise MCPToolError(-32603, str(exception)) from exception
    snapshot = await asyncio.to_thread(
        read_stable_file_snapshot,
        utility_tools,
        normalized_file_path,
        max_bytes=limits.max_source_bytes,
        description="file_path",
    )
    if (
        snapshot.source_size_bytes > limits.max_source_bytes
        or len(snapshot.data) > limits.max_source_bytes
    ):
        raise MCPToolError(
            -32602,
            f"image source exceeds read_image limit ({snapshot.source_size_bytes} bytes > {limits.max_source_bytes} bytes)",
        )
    source_mime_type = snapshot.detected_mime_type or "application/octet-stream"
    if not is_supported_image_candidate(
        path=snapshot.resolved_path,
        content_type=source_mime_type,
    ):
        raise MCPToolError(-32602, "file is not a supported image candidate")
    prepared, failure_reason = await asyncio.to_thread(
        prepare_inline_image_for_prompt_relay,
        image_bytes=snapshot.data,
        declared_content_type=source_mime_type,
        max_source_bytes=limits.max_source_bytes,
        max_encoded_chars=limits.max_encoded_chars,
        max_pixels=limits.max_pixels,
        jpeg_quality=limits.jpeg_quality,
        allow_image_candidate=True,
    )
    if prepared is None:
        raise MCPToolError(-32602, failure_reason or "unsupported or corrupt image")
    image_base64 = prepared.payload.get("image_base64")
    if not isinstance(image_base64, str) or not image_base64:
        raise MCPToolError(-32602, "image encoding failed")
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    files_state = utility_tools.runtime_sessions.get_or_create_workspace_state(owner_key)
    record_file_read_with_signature(files_state, snapshot.resolved_path, snapshot.signature)
    return {
        "path": snapshot.resolved_path,
        "content_type": prepared.content_type,
        "image_base64": image_base64,
        "size_bytes": prepared.prepared_bytes,
        "source_size_bytes": snapshot.source_size_bytes,
        "source_mime_type": source_mime_type,
        "encoded_chars": prepared.encoded_chars,
        "width": prepared.prepared_width,
        "height": prepared.prepared_height,
        "source_width": prepared.source_width,
        "source_height": prepared.source_height,
    }
