"""SoAI - MCP read_file text mode selection [backend/mcp/tools/file_text_reading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.validation.booleans import parse_bool_flag_with_default
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError
from mcp.tools.file_content_classification import classify_read_file_content
from mcp.tools.file_indentation_ranges import select_indentation_range
from mcp.tools.file_read_omission_payloads import build_binary_omitted_payload
from mcp.tools.file_text_response_budget import build_prompt_safe_line_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ReadFileTextOptions",
    "read_text_file_for_tool",
    "require_raw_mode_arguments",
)


@dataclass(frozen=True, slots=True)
class ReadFileTextOptions:
    mode: str
    render: str
    offset: int
    limit: int
    indentation: JSONValue


def require_raw_mode_arguments(arguments: JSONDict) -> None:
    forbidden_keys = ("offset", "limit", "render", "indentation")
    present = [key for key in forbidden_keys if key in arguments and arguments[key] is not None]
    if present:
        raise MCPToolError(
            -32602,
            f"read_file mode=raw reads the full file only and does not accept: {', '.join(present)}. Use mode=slice with render=raw for chunked raw reads.",
        )


def _format_raw_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def _decode_lines(data: bytes) -> list[str]:
    decoded = data.decode("utf-8", errors="replace")
    if not decoded:
        return []
    lines = decoded.split("\n")
    if decoded.endswith("\n"):
        lines.pop()
    return lines


def _read_slice_lines(data: bytes, *, offset: int, limit: int) -> tuple[list[str], int]:
    start_index = max(0, offset - 1)
    end_index = start_index + limit
    lines = _decode_lines(data)
    return lines[start_index:end_index], len(lines)


def _read_raw_file(path: str, data: bytes) -> JSONDict:
    lines = _decode_lines(data)
    total_lines = len(lines)
    content = _format_raw_lines(lines)
    payload: JSONDict = {
        "path": path,
        "mode": "raw",
        "offset": 1,
        "limit": total_lines,
        "total_lines": total_lines,
        "returned_lines": total_lines,
        "start_line": 1 if total_lines > 0 else None,
        "end_line": total_lines if total_lines > 0 else None,
        "next_offset": None,
        "truncated": False,
        "truncation_reason": None,
        "content_truncated": False,
        "serialized_response_chars": 0,
        "max_serialized_response_chars": None,
        "content": content,
    }
    payload["serialized_response_chars"] = len(
        serialize_json_compact_stable_strict(payload, ensure_ascii=False),
    )
    return payload


def _read_binary_metadata_file(
    path: str,
    options: ReadFileTextOptions,
    data: bytes,
) -> JSONDict | None:
    classification = classify_read_file_content(path, data)
    if classification.text_safe:
        return None
    return build_binary_omitted_payload(
        path=path,
        mode=options.mode,
        offset=options.offset,
        limit=options.limit,
        classification=classification,
    )


def _read_slice_file(path: str, options: ReadFileTextOptions, data: bytes) -> JSONDict:
    selected, total_lines = _read_slice_lines(data, offset=options.offset, limit=options.limit)
    start_index = max(0, options.offset - 1)
    start_line = start_index + 1 if selected else None
    return build_prompt_safe_line_payload(
        path=path,
        mode="slice",
        offset=options.offset,
        limit=options.limit,
        total_lines=total_lines,
        selected=selected,
        start_line=start_line,
        render=options.render,
        line_limit_truncated=total_lines > start_index + options.limit,
        indentation=None,
    )


def _read_indentation_file(path: str, options: ReadFileTextOptions, data: bytes) -> JSONDict:
    lines = _decode_lines(data)
    total_lines = len(lines)
    indentation_obj: dict[str, JSONValue] = {}
    if options.indentation is not None and not isinstance(options.indentation, dict):
        raise MCPToolError(-32602, "Indentation must be an object")
    if isinstance(options.indentation, dict):
        indentation_obj = {
            str(key): value for key, value in options.indentation.items() if isinstance(key, str)
        }
    anchor = parse_int(
        indentation_obj.get("anchor_line"),
        default=options.offset,
        min_value=1,
        max_value=max(total_lines, 1),
    )
    max_levels = parse_int(
        indentation_obj.get("max_levels"),
        default=0,
        min_value=0,
        max_value=1000,
    )
    include_siblings = parse_bool_flag_with_default(
        indentation_obj.get("include_siblings"),
        default=False,
    )
    include_header = parse_bool_flag_with_default(
        indentation_obj.get("include_header"),
        default=True,
    )
    max_lines = parse_int(
        indentation_obj.get("max_lines"),
        default=options.limit,
        min_value=1,
        max_value=options.limit,
    )
    indentation_payload: JSONDict = {
        "anchor_line": anchor,
        "max_levels": max_levels,
        "include_siblings": include_siblings,
        "include_header": include_header,
        "max_lines": max_lines,
    }
    if total_lines == 0:
        return build_prompt_safe_line_payload(
            path=path,
            mode="indentation",
            offset=options.offset,
            limit=options.limit,
            total_lines=total_lines,
            selected=[],
            start_line=None,
            render=options.render,
            line_limit_truncated=False,
            indentation=indentation_payload,
        )
    try:
        start_index, end_index, truncated = select_indentation_range(
            lines,
            anchor_line=anchor,
            max_levels=max_levels,
            include_siblings=include_siblings,
            include_header=include_header,
            max_lines=max_lines,
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    selected = lines[start_index : end_index + 1]
    return build_prompt_safe_line_payload(
        path=path,
        mode="indentation",
        offset=options.offset,
        limit=options.limit,
        total_lines=total_lines,
        selected=selected,
        start_line=start_index + 1 if selected else None,
        render=options.render,
        line_limit_truncated=truncated,
        indentation=indentation_payload,
    )


def read_text_file_for_tool(path: str, options: ReadFileTextOptions, data: bytes) -> JSONDict:
    binary_metadata = _read_binary_metadata_file(path, options, data)
    if binary_metadata is not None:
        return binary_metadata
    if options.mode == "raw":
        return _read_raw_file(path, data)
    if options.mode == "slice":
        return _read_slice_file(path, options, data)
    return _read_indentation_file(path, options, data)
