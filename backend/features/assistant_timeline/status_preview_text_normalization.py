"""SoAI - Status preview text normalization [backend/features/assistant_timeline/status_preview_text_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.assistant_timeline.status_preview_constants import (
    STATUS_PREVIEW_TOOL_DETAIL_MAX_CHARS,
)
from features.assistant_timeline.status_preview_text_cleaning import (
    collapse_status_preview_candidate,
    lowercase_subsequent_word_initials,
    strip_status_preview_leading_filler,
    strip_status_preview_leading_list_marker,
    strip_status_preview_wrapping_punctuation,
    strip_system_reminder_blocks,
    truncate_status_preview_after_meta_separators,
    uppercase_status_preview_first_letter,
)

__all__ = ("normalize_status_preview_text",)

STATUS_PREVIEW_MAX_WORDS = 12
STATUS_PREVIEW_MAX_TEXT_CHARS = STATUS_PREVIEW_TOOL_DETAIL_MAX_CHARS
STATUS_PREVIEW_REJECTED_PREFIXES: tuple[str, ...] = (
    "write ",
    "output",
    "label",
    "return",
    "describe",
    "generate",
)
STATUS_PREVIEW_REJECTED_SUBSTRINGS: tuple[str, ...] = (
    "subagent",
    "comprehensive",
    "systematically",
    "coverage",
    "parameters",
    "configurations",
    "report any",
)
STATUS_PREVIEW_REJECTED_REMINDER_SUBSTRINGS: tuple[str, ...] = (
    "system-reminder",
    "operational mode",
    "read-only mode",
    "plan to build",
    "permitted to make file changes",
    "internal ui",
    "constraints",
)


def normalize_status_preview_text(value: str) -> str | None:
    scrubbed = strip_system_reminder_blocks(value)
    normalized = collapse_status_preview_candidate(scrubbed)
    if not normalized:
        return None
    translation_map: dict[str, str | int | None] = {
        ",": " ",
        ";": " ",
        ":": " ",
        "!": " ",
        "?": " ",
        "\t": " ",
        "\n": " ",
    }
    without_punctuation = normalized.translate(str.maketrans(translation_map))
    trimmed = strip_status_preview_leading_list_marker(
        strip_status_preview_wrapping_punctuation(
            truncate_status_preview_after_meta_separators(
                strip_status_preview_leading_filler(without_punctuation),
            ),
        ),
    )
    if not trimmed:
        return None
    if "<" in trimmed or ">" in trimmed:
        return None
    lowered = trimmed.lower()
    if "live activity" in lowered and "label" in lowered:
        return None
    if any(lowered.startswith(prefix) for prefix in STATUS_PREVIEW_REJECTED_PREFIXES):
        return None
    if any(fragment in lowered for fragment in STATUS_PREVIEW_REJECTED_SUBSTRINGS):
        return None
    if any(fragment in lowered for fragment in STATUS_PREVIEW_REJECTED_REMINDER_SUBSTRINGS):
        return None
    if lowered in (
        "thinking",
        "thinking process",
        "processing",
        "working",
        "working on it",
    ):
        return None
    if lowered.startswith("thinking process"):
        return None
    if (
        "action phrase" in lowered
        or "output only" in lowered
        or "start with" in lowered
        or "length" in lowered
    ):
        return None
    words = [word for word in trimmed.split(" ") if word]
    if not words:
        return None
    clamped = " ".join(words[:STATUS_PREVIEW_MAX_WORDS]).strip()
    finalized = strip_status_preview_wrapping_punctuation(clamped)
    if not finalized:
        return None
    cased = lowercase_subsequent_word_initials(uppercase_status_preview_first_letter(finalized))
    if not cased:
        return None
    collapsed = collapse_status_preview_candidate(cased)
    if not collapsed:
        return None
    if len(collapsed) > STATUS_PREVIEW_MAX_TEXT_CHARS:
        collapsed = collapsed[:STATUS_PREVIEW_MAX_TEXT_CHARS].rstrip()
    if not collapsed:
        return None
    if not any(character.isalnum() for character in collapsed):
        return None
    return collapsed
