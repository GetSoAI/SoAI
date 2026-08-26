"""SoAI - Markdown code segment parsing for preview-contract logic [backend/core/formatting/markdown_code_segments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "split_fenced_segments",
    "split_inline_code_segments",
    "strip_fenced_code_blocks",
    "strip_inline_code_spans",
)


def _resolve_fence_open(stripped: str) -> tuple[str, int] | None:
    if not stripped:
        return None
    first = stripped[0]
    if first not in ("`", "~"):
        return None
    count = 0
    for character in stripped:
        if character != first:
            break
        count += 1
    if count < 3:
        return None
    return (first, count)


def strip_fenced_code_blocks(text: str) -> str:
    normalized = str(text or "")
    if not normalized:
        return ""
    lines = normalized.splitlines(keepends=True)
    output: list[str] = []
    active_fence_char: str | None = None
    active_fence_min_len: int = 0
    for line in lines:
        stripped = line.lstrip()
        fence_open = _resolve_fence_open(stripped)
        if active_fence_char is None:
            if fence_open is not None:
                active_fence_char, active_fence_min_len = fence_open
                output.append("\n")
                continue
            output.append(line)
            continue
        if fence_open is not None and fence_open[0] == active_fence_char:
            if fence_open[1] >= active_fence_min_len:
                active_fence_char = None
                active_fence_min_len = 0
                output.append("\n")
                continue
    return "".join(output)


def split_fenced_segments(text: str) -> tuple[tuple[bool, str], ...]:
    normalized = str(text or "")
    if not normalized:
        return ()
    lines = normalized.splitlines(keepends=True)
    segments: list[tuple[bool, str]] = []
    prose_parts: list[str] = []
    fence_parts: list[str] = []
    active_fence_char: str | None = None
    active_fence_min_len = 0
    for line in lines:
        stripped = line.lstrip()
        fence_open = _resolve_fence_open(stripped)
        if active_fence_char is None:
            if fence_open is None:
                prose_parts.append(line)
                continue
            if prose_parts:
                segments.append((False, "".join(prose_parts)))
                prose_parts = []
            active_fence_char, active_fence_min_len = fence_open
            fence_parts.append(line)
            continue
        fence_parts.append(line)
        if fence_open is None:
            continue
        if fence_open[0] != active_fence_char or fence_open[1] < active_fence_min_len:
            continue
        segments.append((True, "".join(fence_parts)))
        fence_parts = []
        active_fence_char = None
        active_fence_min_len = 0
    if fence_parts:
        segments.append((True, "".join(fence_parts)))
    if prose_parts:
        segments.append((False, "".join(prose_parts)))
    return tuple(segments)


def strip_inline_code_spans(text: str) -> str:
    normalized = str(text or "")
    if not normalized:
        return ""
    output: list[str] = []
    length = len(normalized)
    index = 0
    while index < length:
        character = normalized[index]
        if character != "`":
            output.append(character)
            index += 1
            continue
        start = index
        while index < length and normalized[index] == "`":
            index += 1
        delimiter = normalized[start:index]
        end_index = normalized.find(delimiter, index)
        if end_index < 0:
            output.append(delimiter)
            continue
        index = end_index + len(delimiter)
    return "".join(output)


def split_inline_code_segments(text: str) -> tuple[tuple[bool, str], ...]:
    normalized = str(text or "")
    if not normalized:
        return ()
    segments: list[tuple[bool, str]] = []
    prose_parts: list[str] = []
    length = len(normalized)
    index = 0
    while index < length:
        if normalized[index] != "`":
            prose_parts.append(normalized[index])
            index += 1
            continue
        start = index
        while index < length and normalized[index] == "`":
            index += 1
        delimiter = normalized[start:index]
        end_index = normalized.find(delimiter, index)
        if end_index < 0:
            prose_parts.append(delimiter)
            continue
        if prose_parts:
            segments.append((False, "".join(prose_parts)))
            prose_parts = []
        segments.append((True, normalized[start : end_index + len(delimiter)]))
        index = end_index + len(delimiter)
    if prose_parts:
        segments.append((False, "".join(prose_parts)))
    return tuple(segments)
