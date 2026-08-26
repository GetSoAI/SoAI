"""SoAI - MCP file indentation range selection [backend/mcp/tools/file_indentation_ranges.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("select_indentation_range",)


def _indent_width(line: str) -> int:
    width = 0
    for ch in line:
        if ch == " ":
            width += 1
            continue
        if ch == "\t":
            width += 4
            continue
        break
    return width


def _is_blank(line: str) -> bool:
    return not line.strip()


def _find_prev_nonblank(lines: list[str], start_index: int) -> int | None:
    for index in range(start_index, -1, -1):
        if not _is_blank(lines[index]):
            return index
    return None


def _find_next_nonblank(lines: list[str], start_index: int) -> int | None:
    for index in range(start_index, len(lines)):
        if not _is_blank(lines[index]):
            return index
    return None


def select_indentation_range(
    lines: list[str],
    *,
    anchor_line: int,
    max_levels: int,
    include_siblings: bool,
    include_header: bool,
    max_lines: int,
) -> tuple[int, int, bool]:
    total = len(lines)
    anchor_index = anchor_line - 1
    if anchor_index < 0 or anchor_index >= total:
        raise ValidationError(f"anchor_line out of range: {anchor_line}")
    header_index = anchor_index
    current_indent = _indent_width(lines[anchor_index])
    for _ in range(max_levels):
        candidate = _find_prev_nonblank(lines, header_index - 1)
        if candidate is None:
            break
        candidate_indent = _indent_width(lines[candidate])
        if candidate_indent >= current_indent:
            header_index = candidate
            continue
        current_indent = candidate_indent
        header_index = candidate
    start_index = header_index if include_header else anchor_index
    end_index = total - 1
    if include_siblings:
        boundary = _find_next_nonblank(lines, header_index + 1)
        while boundary is not None:
            if _indent_width(lines[boundary]) < current_indent:
                end_index = boundary - 1
                break
            boundary = _find_next_nonblank(lines, boundary + 1)
    else:
        boundary = _find_next_nonblank(lines, header_index + 1)
        while boundary is not None:
            if _indent_width(lines[boundary]) == current_indent:
                end_index = boundary - 1
                break
            boundary = _find_next_nonblank(lines, boundary + 1)
    extracted_count = (end_index - start_index) + 1
    truncated = extracted_count > max_lines
    if truncated:
        end_index = start_index + max_lines - 1
    return (start_index, end_index, truncated)
