"""SoAI - MCP read_video opaque paging cursor encoding and decoding [backend/mcp/tools/read_video_cursor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.base64_values import decode_base64_ascii, encode_base64_ascii
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.validation.integers import is_strict_int
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("ReadVideoCursor", "decode_cursor", "encode_cursor")

_CURSOR_VERSION = "v1"
_INVALID_MESSAGE = "read_video cursor is invalid."


@dataclass(frozen=True, slots=True)
class ReadVideoCursor:
    job_id: str
    frame_offset: int
    segment_offset: int


def encode_cursor(cursor: ReadVideoCursor) -> str:
    mapping: JSONDict = {
        "job_id": cursor.job_id,
        "frame_offset": cursor.frame_offset,
        "segment_offset": cursor.segment_offset,
        "version": _CURSOR_VERSION,
    }
    payload = serialize_json_compact_stable_strict(mapping).encode("utf-8")
    return encode_base64_ascii(payload)


def _require_non_negative_int(value: JSONValue) -> int:
    if not is_strict_int(value):
        raise MCPToolError(-32602, _INVALID_MESSAGE)
    if value < 0:
        raise MCPToolError(-32602, _INVALID_MESSAGE)
    return value


def decode_cursor(raw: str) -> ReadVideoCursor:
    try:
        decoded = decode_base64_ascii(raw, error_message=_INVALID_MESSAGE)
    except ValidationError as exception:
        raise MCPToolError(-32602, _INVALID_MESSAGE) from exception
    try:
        mapping = parse_json_dict(decoded, field="read_video cursor")
    except ValidationError as exception:
        raise MCPToolError(-32602, _INVALID_MESSAGE) from exception
    if mapping.get("version") != _CURSOR_VERSION:
        raise MCPToolError(-32602, _INVALID_MESSAGE)
    job_id = mapping.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise MCPToolError(-32602, _INVALID_MESSAGE)
    frame_offset = _require_non_negative_int(mapping.get("frame_offset"))
    segment_offset = _require_non_negative_int(mapping.get("segment_offset"))
    return ReadVideoCursor(
        job_id=job_id,
        frame_offset=frame_offset,
        segment_offset=segment_offset,
    )
