"""SoAI - Video OCR sampling, adjacent deduplication, and text budgeting [backend/core/media/video_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import unicodedata

from core.errors.exceptions import ValidationError
from core.media.types import (
    OcrFrameText,
    VisibleTextBudgetResult,
    VisibleTextOccurrence,
)
from core.media.uniform_sampling import select_uniform_indices

__all__ = (
    "apply_visible_text_budget",
    "merge_adjacent_visible_text",
)


def _comparison_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(normalized.casefold().split())


def _similar(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 2 or min(len(left), len(right)) < 3:
        return False
    differences = abs(len(left) - len(right))
    for left_char, right_char in zip(left, right, strict=False):
        if left_char != right_char:
            differences += 1
            if differences > 2:
                return False
    return differences <= 2


def merge_adjacent_visible_text(
    frames: tuple[OcrFrameText, ...],
) -> tuple[VisibleTextOccurrence, ...]:
    occurrences: list[VisibleTextOccurrence] = []
    active: VisibleTextOccurrence | None = None
    for frame in frames:
        normalized_text = " ".join(frame.text.split())
        comparison = _comparison_text(normalized_text)
        if not comparison:
            if active is not None:
                occurrences.append(active)
                active = None
            continue
        if active is not None and _similar(_comparison_text(active.text), comparison):
            active = VisibleTextOccurrence(
                start_seconds=active.start_seconds,
                end_seconds=frame.timestamp_seconds,
                text=active.text,
                confidence=max(active.confidence, frame.confidence),
            )
            continue
        if active is not None:
            occurrences.append(active)
        active = VisibleTextOccurrence(
            start_seconds=frame.timestamp_seconds,
            end_seconds=frame.timestamp_seconds,
            text=normalized_text,
            confidence=frame.confidence,
        )
    if active is not None:
        occurrences.append(active)
    return tuple(occurrences)


def _text_chars(occurrences: tuple[VisibleTextOccurrence, ...]) -> int:
    return sum(len(occurrence.text) for occurrence in occurrences)


def apply_visible_text_budget(
    occurrences: tuple[VisibleTextOccurrence, ...],
    *,
    maximum_text_chars: int,
) -> VisibleTextBudgetResult:
    if maximum_text_chars <= 0:
        raise ValidationError("Video OCR text budget must be positive.")
    original_text_chars = _text_chars(occurrences)
    if original_text_chars <= maximum_text_chars:
        return VisibleTextBudgetResult(
            occurrences=occurrences,
            truncated=False,
            original_text_chars=original_text_chars,
            retained_text_chars=original_text_chars,
        )
    proportional_count = max(
        1,
        min(
            len(occurrences),
            maximum_text_chars,
            maximum_text_chars * len(occurrences) // original_text_chars,
        ),
    )
    indices = select_uniform_indices(len(occurrences), proportional_count)
    selected = tuple(occurrences[index] for index in indices)
    selected_text_chars = _text_chars(selected)
    if selected_text_chars <= maximum_text_chars:
        return VisibleTextBudgetResult(
            occurrences=selected,
            truncated=True,
            original_text_chars=original_text_chars,
            retained_text_chars=selected_text_chars,
        )
    clipped_count = min(len(occurrences), maximum_text_chars)
    clipped_indices = select_uniform_indices(len(occurrences), clipped_count)
    base_allocation, remainder = divmod(maximum_text_chars, clipped_count)
    clipped_occurrences: list[VisibleTextOccurrence] = []
    for selected_index, occurrence_index in enumerate(clipped_indices):
        occurrence = occurrences[occurrence_index]
        allocation = base_allocation + (1 if selected_index < remainder else 0)
        clipped_occurrences.append(
            VisibleTextOccurrence(
                start_seconds=occurrence.start_seconds,
                end_seconds=occurrence.end_seconds,
                text=occurrence.text[:allocation],
                confidence=occurrence.confidence,
            ),
        )
    return VisibleTextBudgetResult(
        occurrences=tuple(clipped_occurrences),
        truncated=True,
        original_text_chars=original_text_chars,
        retained_text_chars=_text_chars(tuple(clipped_occurrences)),
    )
