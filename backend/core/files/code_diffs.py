"""SoAI - Unified diff preview helpers for code-editing tools [backend/core/files/code_diffs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_added_file_diff",
    "build_deleted_file_diff",
    "build_updated_file_diff",
    "build_viewed_file_diff",
    "normalize_code_diffs_payload",
)

DEFAULT_CONTEXT_LINES: int = 3
MAX_DIFF_LINES_PER_BLOCK: int = 400
TRUNCATION_MARKER: str = "... (diff truncated)"


def _normalize_lines(content: str) -> list[str]:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return []
    return normalized.splitlines()


def _build_unified_diff_lines(
    *,
    before_lines: list[str],
    after_lines: list[str],
    before_label: str,
    after_label: str,
    context_lines: int,
) -> list[str]:
    return list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=before_label,
            tofile=after_label,
            n=context_lines,
            lineterm="",
        ),
    )


def _truncate_diff_lines(diff_lines: list[str], max_lines: int) -> tuple[list[str], bool]:
    if len(diff_lines) <= max_lines:
        return (diff_lines, False)
    truncated_lines = list(diff_lines[:max_lines])
    truncated_lines.append(TRUNCATION_MARKER)
    return (truncated_lines, True)


def _build_code_diff_entry(
    *,
    path: str,
    operation: str,
    diff_lines: list[str],
    source_truncated: bool = False,
) -> JSONDict | None:
    if not diff_lines:
        return None
    trimmed_path = path.strip()
    if not trimmed_path:
        return None
    truncated_lines, truncated = _truncate_diff_lines(diff_lines, MAX_DIFF_LINES_PER_BLOCK)
    return {
        "path": trimmed_path,
        "operation": operation,
        "diff": "\n".join(truncated_lines),
        "truncated": truncated or source_truncated,
    }


def build_added_file_diff(*, path: str, new_content: str) -> JSONDict | None:
    diff_lines = _build_unified_diff_lines(
        before_lines=[],
        after_lines=_normalize_lines(new_content),
        before_label="/dev/null",
        after_label=path,
        context_lines=DEFAULT_CONTEXT_LINES,
    )
    return _build_code_diff_entry(path=path, operation="added", diff_lines=diff_lines)


def build_deleted_file_diff(*, path: str, old_content: str) -> JSONDict | None:
    diff_lines = _build_unified_diff_lines(
        before_lines=_normalize_lines(old_content),
        after_lines=[],
        before_label=path,
        after_label="/dev/null",
        context_lines=DEFAULT_CONTEXT_LINES,
    )
    return _build_code_diff_entry(path=path, operation="deleted", diff_lines=diff_lines)


def build_updated_file_diff(*, path: str, old_content: str, new_content: str) -> JSONDict | None:
    old_lines = _normalize_lines(old_content)
    new_lines = _normalize_lines(new_content)
    if old_lines == new_lines:
        return None
    diff_lines = _build_unified_diff_lines(
        before_lines=old_lines,
        after_lines=new_lines,
        before_label=path,
        after_label=path,
        context_lines=DEFAULT_CONTEXT_LINES,
    )
    return _build_code_diff_entry(path=path, operation="updated", diff_lines=diff_lines)


def build_viewed_file_diff(
    *,
    path: str,
    viewed_lines: list[tuple[int, str]],
    source_truncated: bool = False,
) -> JSONDict | None:
    normalized_by_line_number: dict[int, str] = {}
    for line_number, text in viewed_lines:
        if line_number < 1 or line_number in normalized_by_line_number:
            continue
        normalized_by_line_number[line_number] = text
    ordered_lines = sorted(normalized_by_line_number.items())
    if not ordered_lines:
        return None
    diff_lines: list[str] = [f"--- {path.strip()}"]
    range_start = 0
    while range_start < len(ordered_lines):
        range_end = range_start
        while (
            range_end + 1 < len(ordered_lines)
            and ordered_lines[range_end + 1][0] == ordered_lines[range_end][0] + 1
        ):
            range_end += 1
        start_line_number = ordered_lines[range_start][0]
        end_line_number = ordered_lines[range_end][0]
        diff_lines.append(f"@@ viewed {start_line_number}-{end_line_number} @@")
        for _, text in ordered_lines[range_start : range_end + 1]:
            diff_lines.append(f">{text}")
        range_start = range_end + 1
    return _build_code_diff_entry(
        path=path,
        operation="viewed",
        diff_lines=diff_lines,
        source_truncated=source_truncated,
    )


def normalize_code_diffs_payload(value: JSONValue) -> list[JSONDict] | None:
    if not isinstance(value, list):
        return None
    normalized: list[JSONDict] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        path_value = entry.get("path")
        diff_value = entry.get("diff")
        if not isinstance(path_value, str) or not path_value.strip():
            continue
        if not isinstance(diff_value, str) or not diff_value:
            continue
        operation_value = entry.get("operation")
        operation_text = operation_value.strip().lower() if isinstance(operation_value, str) else ""
        truncated_value = entry.get("truncated")
        normalized.append(
            {
                "path": path_value.strip(),
                "operation": (
                    operation_text
                    if operation_text in {"added", "deleted", "updated", "viewed"}
                    else "updated"
                ),
                "diff": diff_value,
                "truncated": bool(truncated_value) if isinstance(truncated_value, bool) else False,
            },
        )
    return normalized or None
