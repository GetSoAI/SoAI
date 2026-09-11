"""SoAI - Automation recurrence scheduling [backend/core/automation/automation_recurrence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.automation_constants import AUTOMATION_OCCURRENCES_MAX_ITEMS
from core.automation.automation_local_time import (
    local_naive_from_utc_ms,
    parse_start_local,
    resolve_local_naive_to_utc_ms,
)
from core.automation.automation_recurrence_candidates import (
    advance_occurrence_naive,
    most_recent_occurrence_naive_at_or_before,
    next_occurrence_naive_after,
)
from core.errors.exceptions import OneShotAutomationStartNotFutureError, ValidationError

__all__ = (
    "iter_occurrences_in_window",
    "resolve_due_run_slot_and_next_run_at",
    "resolve_due_run_slots_and_next_run_at",
    "resolve_next_run_at",
)


def resolve_next_run_at(
    *,
    timezone_name: str,
    start_local: str,
    recurrence: str,
    enabled: bool,
    now_ms: int,
) -> int | None:
    if not enabled:
        return None
    start_naive = parse_start_local(start_local)
    if recurrence == "none":
        scheduled_at = resolve_local_naive_to_utc_ms(start_naive, timezone_name)
        if scheduled_at <= now_ms:
            raise OneShotAutomationStartNotFutureError(
                "One-shot automations must start strictly in the future when enabled.",
            )
        return scheduled_at
    now_local_naive = local_naive_from_utc_ms(now_ms, timezone_name)
    candidate_naive = next_occurrence_naive_after(
        start_naive=start_naive,
        recurrence=recurrence,
        pivot_naive=now_local_naive,
        inclusive=False,
    )
    return resolve_local_naive_to_utc_ms(candidate_naive, timezone_name)


def resolve_due_run_slot_and_next_run_at(
    *,
    timezone_name: str,
    start_local: str,
    recurrence: str,
    now_ms: int,
) -> tuple[int, int | None]:
    start_naive = parse_start_local(start_local)
    if recurrence == "none":
        scheduled_at = resolve_local_naive_to_utc_ms(start_naive, timezone_name)
        return (scheduled_at, None)
    now_local_naive = local_naive_from_utc_ms(now_ms, timezone_name)
    due_naive = most_recent_occurrence_naive_at_or_before(
        start_naive=start_naive,
        recurrence=recurrence,
        pivot_naive=now_local_naive,
    )
    next_naive = next_occurrence_naive_after(
        start_naive=start_naive,
        recurrence=recurrence,
        pivot_naive=now_local_naive,
        inclusive=False,
    )
    return (
        resolve_local_naive_to_utc_ms(due_naive, timezone_name),
        resolve_local_naive_to_utc_ms(next_naive, timezone_name),
    )


def resolve_due_run_slots_and_next_run_at(
    *,
    timezone_name: str,
    start_local: str,
    recurrence: str,
    first_next_run_at: int,
    now_ms: int,
    max_slots: int,
) -> tuple[list[int], int | None]:
    if max_slots <= 0:
        raise ValidationError("Automation max_slots must be positive.")
    start_naive = parse_start_local(start_local)
    if recurrence == "none":
        if first_next_run_at > now_ms:
            return ([], first_next_run_at)
        return ([first_next_run_at], None)
    current_next_run_at = first_next_run_at
    current_naive = local_naive_from_utc_ms(current_next_run_at, timezone_name)
    scheduled_slots: list[int] = []
    while current_next_run_at <= now_ms and len(scheduled_slots) < max_slots:
        scheduled_slots.append(current_next_run_at)
        current_naive = next_occurrence_naive_after(
            start_naive=start_naive,
            recurrence=recurrence,
            pivot_naive=current_naive,
            inclusive=False,
        )
        current_next_run_at = resolve_local_naive_to_utc_ms(current_naive, timezone_name)
    return (scheduled_slots, current_next_run_at)


def iter_occurrences_in_window(
    *,
    timezone_name: str,
    start_local: str,
    recurrence: str,
    from_utc_ms: int,
    to_utc_ms: int,
    max_items: int | None = AUTOMATION_OCCURRENCES_MAX_ITEMS,
) -> list[int]:
    if from_utc_ms >= to_utc_ms:
        return []
    if max_items is not None and max_items <= 0:
        raise ValidationError("Automation max_items must be positive.")
    start_naive = parse_start_local(start_local)
    if recurrence == "none":
        scheduled_at = resolve_local_naive_to_utc_ms(start_naive, timezone_name)
        return [scheduled_at] if from_utc_ms <= scheduled_at < to_utc_ms else []
    from_local_naive = local_naive_from_utc_ms(from_utc_ms, timezone_name)
    to_local_naive = local_naive_from_utc_ms(to_utc_ms, timezone_name)
    candidate_naive = next_occurrence_naive_after(
        start_naive=start_naive,
        recurrence=recurrence,
        pivot_naive=from_local_naive,
        inclusive=True,
    )
    occurrences: list[int] = []
    steps_taken = 0
    while candidate_naive < to_local_naive:
        scheduled_at = resolve_local_naive_to_utc_ms(candidate_naive, timezone_name)
        if from_utc_ms <= scheduled_at < to_utc_ms:
            occurrences.append(scheduled_at)
        if max_items is not None and len(occurrences) > max_items:
            raise ValidationError("Automation occurrences exceed the allowed window size.")
        candidate_naive = advance_occurrence_naive(candidate_naive, start_naive, recurrence)
        steps_taken += 1
        if max_items is not None and steps_taken > max_items + 366:
            raise ValidationError("Automation occurrence generation exceeded its safety bound.")
    return occurrences
