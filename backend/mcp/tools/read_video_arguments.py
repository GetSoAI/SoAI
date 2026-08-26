"""SoAI - MCP read_video argument parsing [backend/mcp/tools/read_video_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.tools.argument_fields import optional_non_empty_string
from mcp.tools.argument_scalars import (
    parse_bool_strict_default,
    parse_optional_number_strict,
)
from mcp.tools.files_access import resolve_existing_file
from mcp.tools.read_video_cursor import ReadVideoCursor, decode_cursor

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("ReadVideoArguments", "parse_read_video_arguments")

_MAX_SECONDS = 1_000_000_000.0


@dataclass(frozen=True, slots=True)
class ReadVideoArguments:
    file_path: str
    resolved_path: str | None
    frames_per_second: float | None
    include_audio: bool | None
    start_seconds: float
    end_seconds: float | None
    job_id: str | None
    cursor: ReadVideoCursor | None
    cancel: bool


def _optional_number(arguments: JSONDict, key: str) -> float | None:
    return parse_optional_number_strict(
        arguments.get(key),
        field_name=key,
        min_value=0.0,
        max_value=_MAX_SECONDS,
    )


def _requested_fps(arguments: JSONDict) -> float | None:
    return parse_optional_number_strict(
        arguments.get("frames_per_second"),
        field_name="frames_per_second",
        min_value=0.000001,
        max_value=1.0,
    )


def _decode_cursor(arguments: JSONDict) -> ReadVideoCursor | None:
    raw_cursor = optional_non_empty_string(arguments.get("cursor"), key="cursor")
    if raw_cursor is None:
        return None
    return decode_cursor(raw_cursor)


def _include_audio(arguments: JSONDict) -> bool | None:
    if "include_audio" not in arguments:
        return None
    return parse_bool_strict_default(
        arguments.get("include_audio"),
        field_name="include_audio",
        default=True,
    )


def parse_read_video_arguments(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> ReadVideoArguments:
    file_path = optional_non_empty_string(arguments.get("file_path"), key="file_path") or ""
    resolved_path = (
        resolve_existing_file(utility_tools, file_path, description="file_path")
        if file_path
        else None
    )
    start_seconds = _optional_number(arguments, "start_seconds")
    return ReadVideoArguments(
        file_path=file_path,
        resolved_path=resolved_path,
        frames_per_second=_requested_fps(arguments),
        include_audio=_include_audio(arguments),
        start_seconds=0.0 if start_seconds is None else start_seconds,
        end_seconds=_optional_number(arguments, "end_seconds"),
        job_id=optional_non_empty_string(arguments.get("job_id"), key="job_id"),
        cursor=_decode_cursor(arguments),
        cancel=parse_bool_strict_default(
            arguments.get("cancel"),
            field_name="cancel",
            default=False,
        ),
    )
