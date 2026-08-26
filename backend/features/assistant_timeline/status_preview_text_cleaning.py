"""SoAI - Status preview text cleaning helpers [backend/features/assistant_timeline/status_preview_text_cleaning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.assistant_timeline.status_preview_constants import (
    STATUS_PREVIEW_MAX_EXCERPT_CHARS,
)
from features.assistant_timeline.status_preview_text_primitives import (
    collapse_status_preview_whitespace,
)

__all__ = (
    "collapse_status_preview_candidate",
    "lowercase_subsequent_word_initials",
    "strip_status_preview_leading_filler",
    "strip_status_preview_leading_list_marker",
    "strip_status_preview_wrapping_punctuation",
    "strip_system_reminder_blocks",
    "truncate_status_preview_after_meta_separators",
    "uppercase_status_preview_first_letter",
)


def strip_system_reminder_blocks(value: str) -> str:
    text = str(value or "")
    while True:
        lowered = text.lower()
        open_index = lowered.find("<system-reminder>")
        if open_index < 0:
            break
        close_index = lowered.find("</system-reminder>", open_index)
        if close_index < 0:
            text = text[:open_index]
            break
        after_index = close_index + len("</system-reminder>")
        text = (text[:open_index] + text[after_index:]).strip()

    while True:
        lowered = text.lower()
        open_index = lowered.find("&lt;system-reminder&gt;")
        if open_index < 0:
            break
        close_index = lowered.find("&lt;/system-reminder&gt;", open_index)
        if close_index < 0:
            text = text[:open_index]
            break
        after_index = close_index + len("&lt;/system-reminder&gt;")
        text = (text[:open_index] + text[after_index:]).strip()

    return text


def strip_status_preview_leading_filler(value: str) -> str:
    current = str(value or "").strip()
    if not current:
        return ""
    while True:
        lowered = current.lower().lstrip()
        previous = current
        for prefix in (
            "generate an internal ui status label ",
            "generate a status label ",
            "generate a label ",
            "generate ",
            "describe what's happening ",
            "describe what is happening ",
            "describe what's ",
            "describe ",
            "return only ",
            "return a ",
            "return ",
            "write a live activity label for an assistant turn ",
            "write a live activity label ",
            "write the next live label ",
            "write the next label ",
            "write the label ",
            "write a label ",
            "write a short label ",
            "write an action phrase ",
            "write a short action phrase ",
            "output: ",
            "output ",
            "label: ",
            "label ",
            "the user wants me to ",
            "the user asked me to ",
            "the user is asking me to ",
            "the user wants to ",
            "the user asked to ",
            "the user is asking to ",
            "user wants me to ",
            "user asked me to ",
            "user is asking me to ",
            "user wants to ",
            "user asked to ",
            "user is asking to ",
            "wants me to ",
            "asked me to ",
            "asking me to ",
            "wants to ",
            "asked to ",
            "asking to ",
            "the user is ",
            "user is ",
            "the user ",
            "user ",
            "i'm ",
            "im ",
            "i am ",
            "i will ",
            "i'll ",
            "i ",
            "we're ",
            "we are ",
            "we will ",
            "we'll ",
            "we ",
            "you are ",
            "you're ",
            "you ",
            "to ",
        ):
            if lowered.startswith(prefix):
                current = current[len(prefix) :].lstrip()
                break
        if current == previous:
            return current


def truncate_status_preview_after_meta_separators(value: str) -> str:
    current = str(value or "").strip()
    if not current:
        return ""
    lowered = current.lower()
    earliest_index: int | None = None
    for needle in (
        " but ",
        " because ",
        " so that ",
        "system-reminder",
        "<system-reminder",
        " system-reminder ",
        " operational mode ",
        " read-only mode ",
        " plan to build ",
        " permitted to make file changes ",
        " internal ui ",
        " constraints ",
        " action phrase ",
        " instructions ",
        " explanation ",
        " explain ",
        " output only ",
        " start with ",
        " length ",
        " need to ",
        " have to ",
        " i ",
        " we ",
        " you ",
        " wants me to ",
        " asked me to ",
        " asking me to ",
        " the user ",
        " user ",
    ):
        index = lowered.find(needle)
        if index < 0:
            continue
        if earliest_index is None or index < earliest_index:
            earliest_index = index
    if earliest_index is None:
        return current
    return current[:earliest_index].rstrip()


def strip_status_preview_leading_list_marker(value: str) -> str:
    normalized = str(value or "").lstrip()
    index = 0
    while index < len(normalized) and normalized[index].isdigit():
        index += 1
    if index < 1:
        return normalized
    marker = normalized[:index]
    remainder = normalized[index:]
    if (
        not remainder.startswith(". ")
        and not remainder.startswith(") ")
        and not remainder.startswith("- ")
    ):
        return normalized
    if not marker.isdigit():
        return normalized
    return remainder[2:].lstrip()


def strip_status_preview_wrapping_punctuation(value: str) -> str:
    normalized = str(value or "").strip()
    while normalized and normalized[0] in "\"'`“”‘’*-•([{":
        normalized = normalized[1:].lstrip()
    while normalized and normalized[-1] in "\"'`“”‘’.,;:!?…)]}":
        normalized = normalized[:-1].rstrip()
    return normalized


def uppercase_status_preview_first_letter(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    first = normalized[0]
    if first.isalpha():
        return first.upper() + normalized[1:]
    return normalized


def lowercase_subsequent_word_initials(value: str) -> str:
    words = [word for word in str(value or "").split(" ") if word]
    if len(words) <= 1:
        return " ".join(words)
    normalized: list[str] = [words[0]]
    for word in words[1:]:
        if not word:
            continue
        first = word[0]
        remainder = word[1:]
        if first.isalpha() and remainder and remainder.islower():
            normalized.append(first.lower() + remainder)
        else:
            normalized.append(word)
    return " ".join(normalized)


def collapse_status_preview_candidate(value: str) -> str:
    return collapse_status_preview_whitespace(
        value,
        max_chars=STATUS_PREVIEW_MAX_EXCERPT_CHARS,
    )
