"""SoAI - Thinking preface sentence and list boundary detection [backend/core/openai/thinking_preface_boundaries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.openai.thinking_preface_numbered_points import (
    resolve_incomplete_numbered_list_item_start,
    resolve_numbered_point_sentence_end_skip,
)
from core.openai.thinking_preface_text_scan import (
    is_ascii_digit,
    resolve_next_visible_index,
    resolve_previous_visible_index,
)

_WRAPPED_IDENTIFIER_FRAGMENT_PATTERN: str = (
    r"([A-Za-z0-9_/-]*[_/-][A-Za-z0-9_/-]*)\.[ \t]*\n[ \t]*([a-z0-9])"
)
_NUMBERED_MARKER_PATTERN: str = r"(^|[\s:;,(\[{])(\d{1,3})\.[ \t]+"
_TRAILING_NUMBERED_MARKER_PATTERN: str = r"(^|[\s:;,(\[{])(\d{1,3})\.[ \t]*$"
_SENTENCE_END_CHAR: str = "."

__all__ = (
    "normalize_wrapped_identifier_fragments",
    "resolve_incomplete_thinking_preface_end_index",
    "resolve_limited_thinking_preface_bounds",
    "resolve_thinking_preface_bounds",
)


def _resolve_word_start(text: str, end_index: int) -> int:
    cursor = end_index
    while cursor > 0:
        character = text[cursor - 1]
        if character.isalnum() or character in {"_", "-", "/"}:
            cursor -= 1
            continue
        break
    return cursor


def _is_wrapped_identifier_fragment(text: str, dot_index: int) -> bool:
    next_visible_index = resolve_next_visible_index(text, dot_index + 1)
    if next_visible_index is None:
        return False
    if "\n" not in text[dot_index + 1 : next_visible_index]:
        return False
    next_character = text[next_visible_index]
    if not (("a" <= next_character <= "z") or is_ascii_digit(next_character)):
        return False
    previous_visible_index = resolve_previous_visible_index(text, dot_index)
    if previous_visible_index is None:
        return False
    word_start = _resolve_word_start(text, previous_visible_index + 1)
    previous_token = text[word_start : previous_visible_index + 1]
    return "_" in previous_token or "/" in previous_token or "-" in previous_token


def _is_inside_inline_code_span(text: str, dot_index: int) -> bool:
    return text[:dot_index].count("`") % 2 == 1 and "`" in text[dot_index + 1 :]


def _is_inside_double_quoted_span(text: str, dot_index: int) -> bool:
    return text[:dot_index].count('"') % 2 == 1 and '"' in text[dot_index + 1 :]


def normalize_wrapped_identifier_fragments(value: str) -> str:
    return re.sub(_WRAPPED_IDENTIFIER_FRAGMENT_PATTERN, r"\1.\2", value)


def resolve_incomplete_thinking_preface_end_index(text: str) -> int:
    newline_index = text.find("\n")
    if newline_index == -1:
        trailing_numbered_point_start = resolve_incomplete_numbered_list_item_start(text)
        return (
            trailing_numbered_point_start
            if trailing_numbered_point_start is not None
            else len(text)
        )
    previous_visible_index = resolve_previous_visible_index(text, newline_index)
    if previous_visible_index is None or text[previous_visible_index] != _SENTENCE_END_CHAR:
        return newline_index
    if not (
        _is_wrapped_identifier_fragment(text, previous_visible_index)
        or _is_inside_inline_code_span(text, previous_visible_index)
        or _is_inside_double_quoted_span(text, previous_visible_index)
    ):
        return newline_index
    next_visible_index = resolve_next_visible_index(text, newline_index + 1)
    if next_visible_index is None:
        return newline_index
    next_newline_index = text.find("\n", next_visible_index + 1)
    return next_newline_index if next_newline_index != -1 else len(text)


def _resolve_numbered_preface_limit_index(
    text: str,
    sentence_limit: int,
) -> tuple[int | None, bool]:
    expected_value = 1
    consumed_count = 0
    for match in re.finditer(_NUMBERED_MARKER_PATTERN, text):
        marker_dot_index = match.start(2) + len(match.group(2))
        if _is_inside_inline_code_span(text, marker_dot_index) or _is_inside_double_quoted_span(
            text,
            marker_dot_index,
        ):
            continue
        marker_value = int(match.group(2))
        if marker_value != expected_value:
            expected_value = 1
            consumed_count = 0
            if marker_value != expected_value:
                continue
        consumed_count += 1
        if consumed_count > sentence_limit:
            marker_start = match.start(2)
            cursor = marker_start
            while cursor > 0 and text[cursor - 1].isspace():
                cursor -= 1
            return cursor, True
        expected_value += 1
    return None, consumed_count > 0


def _resolve_trailing_incomplete_numbered_marker_start(text: str) -> int | None:
    trailing_match = re.search(_TRAILING_NUMBERED_MARKER_PATTERN, text)
    if trailing_match is None:
        return None
    marker_dot_index = trailing_match.start(2) + len(trailing_match.group(2))
    if _is_inside_inline_code_span(text, marker_dot_index) or _is_inside_double_quoted_span(
        text,
        marker_dot_index,
    ):
        return None
    marker_value = int(trailing_match.group(2))
    if marker_value <= 1:
        return None
    prefix = text[: trailing_match.start(2)]
    expected_value = 1
    consumed_count = 0
    for match in re.finditer(_NUMBERED_MARKER_PATTERN, prefix):
        prefix_marker_dot_index = match.start(2) + len(match.group(2))
        if _is_inside_inline_code_span(
            prefix,
            prefix_marker_dot_index,
        ) or _is_inside_double_quoted_span(prefix, prefix_marker_dot_index):
            continue
        prefix_marker_value = int(match.group(2))
        if prefix_marker_value != expected_value:
            expected_value = 1
            consumed_count = 0
            if prefix_marker_value != expected_value:
                continue
        consumed_count += 1
        expected_value += 1
    if consumed_count == 0 or expected_value != marker_value:
        return None
    cursor = trailing_match.start(2)
    while cursor > 0 and text[cursor - 1].isspace():
        cursor -= 1
    return cursor


def resolve_limited_thinking_preface_bounds(
    text: str,
    *,
    sentence_limit: int,
) -> tuple[int, int, bool] | None:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized or sentence_limit <= 0:
        return None
    numbered_limit_index, has_numbered_preface = _resolve_numbered_preface_limit_index(
        normalized,
        sentence_limit,
    )
    if numbered_limit_index is not None:
        return numbered_limit_index, numbered_limit_index, True
    if has_numbered_preface:
        trailing_marker_start = _resolve_trailing_incomplete_numbered_marker_start(normalized)
        if trailing_marker_start is not None:
            return trailing_marker_start, len(normalized), False
        return len(normalized), len(normalized), False
    cursor = 0
    preface_end_index = 0
    body_start_index = 0
    preface_complete = False
    for _ in range(sentence_limit):
        while cursor < len(normalized) and normalized[cursor].isspace():
            cursor += 1
        if cursor >= len(normalized):
            body_start_index = cursor
            preface_complete = True
            break
        remaining = normalized[cursor:]
        bounds = resolve_thinking_preface_bounds(remaining)
        if bounds is None:
            incomplete_end_index = resolve_incomplete_thinking_preface_end_index(remaining)
            preface_end_index = cursor + incomplete_end_index
            body_start_index = preface_end_index
            preface_complete = False
            break
        preface_end, body_start = bounds
        preface_end_index = cursor + preface_end
        body_start_index = cursor + body_start
        cursor = body_start_index
        preface_complete = True
    return preface_end_index, body_start_index, preface_complete


def resolve_thinking_preface_bounds(text: str) -> tuple[int, int] | None:
    if not text:
        return None
    sentence_start = 0
    cursor = 0
    last_numbered_point_value: int | None = None
    while cursor < len(text):
        character = text[cursor]
        if character == _SENTENCE_END_CHAR:
            next_character = text[cursor + 1] if cursor + 1 < len(text) else None
            if next_character is None or next_character.isspace():
                if _is_inside_inline_code_span(text, cursor):
                    cursor += 1
                    continue
                if _is_inside_double_quoted_span(text, cursor):
                    cursor += 1
                    continue
                if _is_wrapped_identifier_fragment(text, cursor):
                    cursor += 1
                    continue
                numbered_point_skip = resolve_numbered_point_sentence_end_skip(
                    text,
                    cursor,
                    sentence_start,
                    last_numbered_point_value=last_numbered_point_value,
                )
                if numbered_point_skip[0]:
                    if numbered_point_skip[2] is not None:
                        last_numbered_point_value = numbered_point_skip[2]
                    cursor += 1
                    continue
                return cursor + 1, cursor + 1
        cursor += 1
    return None
