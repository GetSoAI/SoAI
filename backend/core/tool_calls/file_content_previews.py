"""SoAI - Tool result projections for viewed file content [backend/core/tool_calls/file_content_previews.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.code_diffs import build_viewed_file_diff, normalize_code_diffs_payload
from core.tool_calls.tool_name_policy import normalize_tool_leaf_name
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("resolve_tool_activity_code_diffs",)


def _normalize_content_lines(content: str) -> list[str]:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.split("\n")


def _build_read_file_preview(result: JSONDict) -> list[JSONDict] | None:
    if result.get("binary") is True or result.get("content_omitted") is True:
        return None
    path_value = result.get("path")
    content_value = result.get("content")
    start_line_value = result.get("start_line")
    returned_lines_value = result.get("returned_lines")
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    if not isinstance(content_value, str):
        return None
    if not is_strict_int(start_line_value) or start_line_value < 1:
        return None
    if not is_strict_int(returned_lines_value) or returned_lines_value < 1:
        return None
    content_lines = _normalize_content_lines(content_value)
    viewed_lines = [
        (start_line_value + line_offset, text) for line_offset, text in enumerate(content_lines)
    ]
    preview = build_viewed_file_diff(
        path=path_value,
        viewed_lines=viewed_lines,
        source_truncated=(
            result.get("truncated") is True or result.get("content_truncated") is True
        ),
    )
    return [preview] if preview is not None else None


def _expand_grep_line(line_value: JSONDict) -> list[tuple[int, str]]:
    line_number_value = line_value.get("line_number")
    text_value = line_value.get("text")
    if not is_strict_int(line_number_value) or line_number_value < 1:
        return []
    if not isinstance(text_value, str):
        return []
    return [
        (line_number_value + line_offset, text)
        for line_offset, text in enumerate(_normalize_content_lines(text_value))
    ]


def _build_grep_file_preview(
    file_value: JSONDict,
    *,
    source_truncated: bool,
) -> JSONDict | None:
    path_value = file_value.get("path")
    lines_value = file_value.get("lines")
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    if not isinstance(lines_value, list):
        return None
    viewed_lines: list[tuple[int, str]] = []
    for line_value in lines_value:
        if isinstance(line_value, dict):
            viewed_lines.extend(_expand_grep_line(line_value))
    return build_viewed_file_diff(
        path=path_value,
        viewed_lines=viewed_lines,
        source_truncated=source_truncated,
    )


def _build_grep_files_previews(result: JSONDict) -> list[JSONDict] | None:
    if result.get("output_mode") != "content":
        return None
    files_value = result.get("files")
    if not isinstance(files_value, list):
        return None
    previews: list[JSONDict] = []
    for file_value in files_value:
        if not isinstance(file_value, dict):
            continue
        preview = _build_grep_file_preview(
            file_value,
            source_truncated=result.get("truncated") is True,
        )
        if preview is not None:
            previews.append(preview)
    return previews or None


def resolve_tool_activity_code_diffs(
    tool_name: str,
    result_payload: JSONValue,
) -> list[JSONDict] | None:
    if not isinstance(result_payload, dict):
        return None
    explicit_diffs = normalize_code_diffs_payload(result_payload.get("code_diffs"))
    if explicit_diffs is not None:
        return explicit_diffs
    tool_leaf_name = normalize_tool_leaf_name(tool_name)
    if tool_leaf_name == "read_file":
        return _build_read_file_preview(result_payload)
    if tool_leaf_name == "grep_files":
        return _build_grep_files_previews(result_payload)
    return None
