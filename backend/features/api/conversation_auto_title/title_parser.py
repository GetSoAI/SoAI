"""SoAI - Auto-title response parsing [backend/features/api/conversation_auto_title/title_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.serialization.json_parsing import parse_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("parse_auto_title",)

_MAX_TITLE_CHARS = 100
_TRUNCATED_TITLE_CHARS = 97
_MIN_TITLE_WORDS = 2
_MAX_TITLE_WORDS = 5
LOGGER_NAME = "SoAI.features.api.title_parser"


def _normalize_title(value: str) -> tuple[str | None, str | None, int, int]:
    collapsed = " ".join(value.split())
    if not collapsed:
        return (None, "empty_title", 0, 0)
    words = collapsed.split(" ")
    word_count = len(words)
    if word_count < _MIN_TITLE_WORDS:
        return (None, "too_few_words", word_count, len(collapsed))
    if word_count > _MAX_TITLE_WORDS:
        collapsed = " ".join(words[:_MAX_TITLE_WORDS])
        words = collapsed.split(" ")
        word_count = len(words)
    if len(collapsed) <= _MAX_TITLE_CHARS:
        return (collapsed, None, word_count, len(collapsed))
    return (f"{collapsed[:_TRUNCATED_TITLE_CHARS]}...", None, word_count, len(collapsed))


def _parse_candidate(candidate: str) -> JSONDict | None:
    try:
        return parse_json_dict(candidate, field="auto title response")
    except ValidationError:
        return None


def _iter_json_object_candidates(raw: str) -> list[str]:
    candidates: list[str] = [raw]
    start_index: int | None = None
    brace_depth = 0
    for index, character in enumerate(raw):
        if character == "{":
            if brace_depth == 0:
                start_index = index
            brace_depth += 1
            continue
        if character != "}":
            continue
        if brace_depth == 0:
            continue
        brace_depth -= 1
        if brace_depth != 0 or start_index is None:
            continue
        candidate = raw[start_index : index + 1]
        if candidate != raw:
            candidates.append(candidate)
        start_index = None
    return candidates


def parse_auto_title(raw: str) -> str | None:
    normalized_raw = str(raw or "").strip()
    if not normalized_raw:
        return None
    logger = get_logger(LOGGER_NAME)
    for candidate in _iter_json_object_candidates(normalized_raw):
        parsed = _parse_candidate(candidate)
        if parsed is None:
            continue
        title_value = parsed.get("title")
        if not isinstance(title_value, str):
            for key, value in parsed.items():
                if not isinstance(key, str):
                    continue
                if key.lower() != "title":
                    continue
                if isinstance(value, str):
                    title_value = value
                    break
        if not isinstance(title_value, str):
            continue
        normalized_title, rejection_reason, word_count, char_count = _normalize_title(title_value)
        if normalized_title is not None:
            return normalized_title
        if rejection_reason is not None:
            logger.debug(
                "Auto-title candidate rejected: reason=%s words=%s chars=%s",
                rejection_reason,
                word_count,
                char_count,
            )
    logger.debug(
        "Auto-title response rejected: reason=no_valid_json_title chars=%s",
        len(normalized_raw),
    )
    return None
