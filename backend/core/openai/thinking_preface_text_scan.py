"""SoAI - Shared text scanning helpers for thinking preface parsing [backend/core/openai/thinking_preface_text_scan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "is_ascii_alphanumeric",
    "is_ascii_digit",
    "resolve_next_visible_index",
    "resolve_previous_visible_index",
)


def is_ascii_digit(character: str) -> bool:
    return "0" <= character <= "9"


def is_ascii_alphanumeric(character: str) -> bool:
    return is_ascii_digit(character) or ("A" <= character <= "Z") or ("a" <= character <= "z")


def resolve_previous_visible_index(text: str, start_index: int) -> int | None:
    cursor = start_index - 1
    while cursor >= 0:
        if not text[cursor].isspace():
            return cursor
        cursor -= 1
    return None


def resolve_next_visible_index(text: str, start_index: int) -> int | None:
    cursor = start_index
    while cursor < len(text):
        if not text[cursor].isspace():
            return cursor
        cursor += 1
    return None
