"""SoAI - Thinking preface inline display rules [backend/core/openai/thinking_preface_display.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.openai.thinking_preface_boundaries import (
    normalize_wrapped_identifier_fragments,
)

INLINE_THINKING_PREFACE_MAX_CHARS: int = 360
TRUNCATED_THINKING_PREFACE_SUFFIX: str = "..."
_MARKDOWN_BLOCK_PREFIXES: tuple[str, ...] = ("#", "-", "*", "+", ">", "|", "```", "~~~")
_PREVIEW_TOKEN_MARKER: str = "[[preview:"

__all__ = (
    "INLINE_THINKING_PREFACE_MAX_CHARS",
    "TRUNCATED_THINKING_PREFACE_SUFFIX",
    "is_inline_safe_thinking_preface",
    "is_truncated_preface_display",
    "normalize_thinking_preface_display_text",
    "normalize_thinking_preface_sentence",
    "resolve_preface_body_display_text",
    "resolve_preface_match_text",
    "resolve_short_preface_only_text",
    "truncate_inline_thinking_preface",
)


def normalize_thinking_preface_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_wrapped_identifier_fragments(value)).strip()


def normalize_thinking_preface_display_text(value: str) -> str:
    normalized = normalize_thinking_preface_sentence(value)
    if not normalized or normalized.endswith("."):
        return normalized
    return f"{normalized}."


def _starts_with_markdown_block_prefix(line: str) -> bool:
    stripped = line.lstrip()
    if not stripped:
        return False
    if stripped.startswith(_MARKDOWN_BLOCK_PREFIXES):
        return True
    return bool(re.match(r"^\d{1,3}[.)][ \t]+", stripped))


def _contains_block_markdown(value: str) -> bool:
    if _PREVIEW_TOKEN_MARKER in value:
        return True
    for line in value.replace("\r\n", "\n").split("\n"):
        if _starts_with_markdown_block_prefix(line):
            return True
    return False


def is_inline_safe_thinking_preface(value: str) -> bool:
    normalized = normalize_thinking_preface_sentence(value)
    if not normalized:
        return False
    if "\n" in value or "\r" in value:
        return False
    if _contains_block_markdown(value):
        return False
    return True


def truncate_inline_thinking_preface(value: str) -> str:
    normalized = normalize_thinking_preface_sentence(value)
    if len(normalized) <= INLINE_THINKING_PREFACE_MAX_CHARS:
        return normalize_thinking_preface_display_text(normalized)
    end_index = max(
        0,
        INLINE_THINKING_PREFACE_MAX_CHARS - len(TRUNCATED_THINKING_PREFACE_SUFFIX),
    )
    sliced = normalized[:end_index]
    last_space = sliced.rfind(" ")
    word_boundary = sliced[:last_space] if last_space > 0 else sliced
    return f"{word_boundary.rstrip()}{TRUNCATED_THINKING_PREFACE_SUFFIX}"


def resolve_preface_match_text(value: str) -> str:
    normalized = normalize_thinking_preface_sentence(value)
    if normalized.endswith(TRUNCATED_THINKING_PREFACE_SUFFIX):
        return normalized[: -len(TRUNCATED_THINKING_PREFACE_SUFFIX)].rstrip()
    return normalized


def is_truncated_preface_display(
    source_preface_text: str,
    display_preface_text: str,
) -> bool:
    if not display_preface_text.endswith(TRUNCATED_THINKING_PREFACE_SUFFIX):
        return False
    if display_preface_text != source_preface_text:
        return True
    return len(source_preface_text) >= INLINE_THINKING_PREFACE_MAX_CHARS


def _join_preface_body(preface_tail: str, body_text: str) -> str:
    normalized_preface_tail = preface_tail.strip()
    normalized_body_text = body_text.strip()
    if not normalized_preface_tail:
        return normalized_body_text
    if not normalized_body_text:
        return normalized_preface_tail
    return f"{normalized_preface_tail} {normalized_body_text}"


def resolve_preface_body_display_text(
    source_preface_text: str,
    display_preface_text: str,
    body_text: str,
    *,
    is_truncated_preface: bool,
) -> str:
    if not is_truncated_preface:
        return body_text
    if source_preface_text.endswith(TRUNCATED_THINKING_PREFACE_SUFFIX):
        if body_text.startswith(TRUNCATED_THINKING_PREFACE_SUFFIX):
            return body_text
        return f"{TRUNCATED_THINKING_PREFACE_SUFFIX}{body_text}"
    visible_preface_text = resolve_preface_match_text(display_preface_text)
    if not visible_preface_text or not source_preface_text.startswith(visible_preface_text):
        return body_text
    omitted_preface_text = source_preface_text[len(visible_preface_text) :].lstrip()
    if not omitted_preface_text:
        return body_text
    coupled_preface_tail = f"{TRUNCATED_THINKING_PREFACE_SUFFIX}{omitted_preface_text}"
    if body_text.startswith(coupled_preface_tail):
        return body_text
    if body_text.startswith(omitted_preface_text):
        return f"{TRUNCATED_THINKING_PREFACE_SUFFIX}{body_text}"
    return _join_preface_body(coupled_preface_tail, body_text)


def resolve_short_preface_only_text(text: str) -> str | None:
    display_text = normalize_thinking_preface_sentence(text)
    if not display_text:
        return None
    if len(display_text) > INLINE_THINKING_PREFACE_MAX_CHARS:
        return None
    if _contains_block_markdown(text):
        return None
    return normalize_thinking_preface_display_text(display_text)
