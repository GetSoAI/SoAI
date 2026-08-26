"""SoAI - Thinking preface numbered-list detection [backend/core/openai/thinking_preface_numbered_points.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.thinking_preface_text_scan import (
    is_ascii_alphanumeric,
    is_ascii_digit,
    resolve_next_visible_index,
    resolve_previous_visible_index,
)

_SENTENCE_END_CHAR: str = "."
_NUMBERED_POINT_MAX_DIGITS: int = 3
_NUMBERED_POINT_CONTEXT_CHARS: frozenset[str] = frozenset(":,;([{")
_NUMBERED_POINT_SEPARATOR_CHARS: frozenset[str] = frozenset(",;:")

__all__ = (
    "has_following_numbered_point_after_sentence_end",
    "resolve_following_numbered_point_details",
    "resolve_incomplete_numbered_list_item_start",
    "resolve_numbered_point_at_sentence_end",
    "resolve_numbered_point_details",
    "resolve_numbered_point_sentence_end_skip",
)


def _trim_numbered_point_separator(text: str, marker_start: int, sentence_start: int) -> int:
    cursor = marker_start
    while cursor > sentence_start and text[cursor - 1].isspace():
        cursor -= 1
    if cursor > sentence_start and text[cursor - 1] in _NUMBERED_POINT_SEPARATOR_CHARS:
        cursor -= 1
    while cursor > sentence_start and text[cursor - 1].isspace():
        cursor -= 1
    return cursor


def resolve_numbered_point_details(
    text: str,
    dot_index: int,
    sentence_start: int,
    *,
    expected_value: int | None,
) -> tuple[int, int] | None:
    digit_start = dot_index
    digit_count = 0
    while digit_start > 0 and is_ascii_digit(text[digit_start - 1]):
        if digit_count >= _NUMBERED_POINT_MAX_DIGITS:
            return None
        digit_start -= 1
        digit_count += 1
    if digit_count == 0:
        return None
    numbered_point_value = int(text[digit_start:dot_index])
    if expected_value is not None and numbered_point_value != expected_value:
        return None
    previous_character = text[digit_start - 1] if digit_start > 0 else None
    if previous_character is not None and is_ascii_alphanumeric(previous_character):
        return None
    previous_visible_index = resolve_previous_visible_index(text, digit_start)
    if previous_visible_index is None or previous_visible_index < sentence_start:
        return digit_start, numbered_point_value
    previous_visible_character = text[previous_visible_index]
    if previous_visible_character in _NUMBERED_POINT_CONTEXT_CHARS:
        return digit_start, numbered_point_value
    if previous_visible_character == _SENTENCE_END_CHAR and expected_value is not None:
        return digit_start, numbered_point_value
    return None


def resolve_following_numbered_point_details(
    text: str,
    start_index: int,
    sentence_start: int,
    *,
    expected_value: int | None,
) -> tuple[int, int] | None:
    digit_start = resolve_next_visible_index(text, start_index)
    if digit_start is None or not is_ascii_digit(text[digit_start]):
        return None
    cursor = digit_start
    digit_count = 0
    while cursor < len(text) and is_ascii_digit(text[cursor]):
        digit_count += 1
        if digit_count > _NUMBERED_POINT_MAX_DIGITS:
            return None
        cursor += 1
    if digit_count == 0 or cursor >= len(text) or text[cursor] != _SENTENCE_END_CHAR:
        return None
    next_character = text[cursor + 1] if cursor + 1 < len(text) else None
    if next_character is None or not next_character.isspace():
        return None
    return resolve_numbered_point_details(
        text,
        cursor,
        sentence_start,
        expected_value=expected_value,
    )


def resolve_numbered_point_at_sentence_end(
    text: str,
    dot_index: int,
    sentence_start: int,
    *,
    last_numbered_point_value: int | None,
) -> tuple[int, int] | None:
    return resolve_numbered_point_details(
        text,
        dot_index,
        sentence_start,
        expected_value=(
            last_numbered_point_value + 1 if last_numbered_point_value is not None else None
        ),
    )


def has_following_numbered_point_after_sentence_end(
    text: str,
    dot_index: int,
    sentence_start: int,
    *,
    last_numbered_point_value: int | None,
) -> bool:
    if last_numbered_point_value is None:
        return False
    following_numbered_point = resolve_following_numbered_point_details(
        text,
        dot_index + 1,
        sentence_start,
        expected_value=last_numbered_point_value + 1,
    )
    return following_numbered_point is not None


def resolve_numbered_point_sentence_end_skip(
    text: str,
    dot_index: int,
    sentence_start: int,
    *,
    last_numbered_point_value: int | None,
) -> tuple[bool, int | None, int | None]:
    numbered_point = resolve_numbered_point_at_sentence_end(
        text,
        dot_index,
        sentence_start,
        last_numbered_point_value=last_numbered_point_value,
    )
    if numbered_point is not None:
        numbered_point_start, numbered_point_value = numbered_point
        return True, numbered_point_start, numbered_point_value
    if has_following_numbered_point_after_sentence_end(
        text,
        dot_index,
        sentence_start,
        last_numbered_point_value=last_numbered_point_value,
    ):
        return True, None, None
    return False, None, None


def resolve_incomplete_numbered_list_item_start(text: str) -> int | None:
    sentence_start = 0
    sequence_sentence_start = 0
    completed_numbered_item_count = 0
    pending_numbered_point_start: int | None = None
    last_numbered_point_value: int | None = None
    cursor = 0
    while cursor < len(text):
        character = text[cursor]
        if character == _SENTENCE_END_CHAR:
            next_character = text[cursor + 1] if cursor + 1 < len(text) else None
            if next_character is None or next_character.isspace():
                (
                    should_skip_sentence_end,
                    numbered_point_start,
                    numbered_point_value,
                ) = resolve_numbered_point_sentence_end_skip(
                    text,
                    cursor,
                    sentence_start,
                    last_numbered_point_value=last_numbered_point_value,
                )
                if should_skip_sentence_end:
                    if numbered_point_value is not None and numbered_point_start is not None:
                        pending_numbered_point_start = numbered_point_start
                        if last_numbered_point_value is None:
                            sequence_sentence_start = sentence_start
                        else:
                            completed_numbered_item_count += 1
                        last_numbered_point_value = numbered_point_value
                    cursor += 1
                    continue
                sentence_start = cursor + 1
                sequence_sentence_start = 0
                completed_numbered_item_count = 0
                pending_numbered_point_start = None
                last_numbered_point_value = None
        cursor += 1
    if (
        last_numbered_point_value is None
        or completed_numbered_item_count < 1
        or pending_numbered_point_start is None
    ):
        return None
    return _trim_numbered_point_separator(
        text,
        pending_numbered_point_start,
        sequence_sentence_start,
    )
