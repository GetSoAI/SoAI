"""SoAI - Automation recurrence candidate math [backend/core/automation/automation_recurrence_candidates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import datetime, timedelta

from core.automation.automation_local_time import last_day_of_month
from core.errors.exceptions import ValidationError

__all__ = (
    "advance_occurrence_naive",
    "most_recent_occurrence_naive_at_or_before",
    "next_occurrence_naive_after",
)


def next_occurrence_naive_after(
    *,
    start_naive: datetime,
    recurrence: str,
    pivot_naive: datetime,
    inclusive: bool,
) -> datetime:
    if recurrence == "hourly":
        return _resolve_hourly_candidate(start_naive, pivot_naive, inclusive=inclusive)
    if recurrence == "daily":
        return _resolve_daily_candidate(start_naive, pivot_naive, inclusive=inclusive)
    if recurrence == "weekly":
        return _resolve_weekly_candidate(start_naive, pivot_naive, inclusive=inclusive)
    if recurrence == "monthly":
        return _resolve_monthly_candidate(start_naive, pivot_naive, inclusive=inclusive)
    if recurrence == "yearly":
        return _resolve_yearly_candidate(start_naive, pivot_naive, inclusive=inclusive)
    raise ValidationError(f"Unsupported automation recurrence '{recurrence}'.")


def most_recent_occurrence_naive_at_or_before(
    *,
    start_naive: datetime,
    recurrence: str,
    pivot_naive: datetime,
) -> datetime:
    candidate = next_occurrence_naive_after(
        start_naive=start_naive,
        recurrence=recurrence,
        pivot_naive=pivot_naive,
        inclusive=True,
    )
    if candidate <= pivot_naive:
        return candidate
    return advance_occurrence_naive(candidate, start_naive, recurrence, reverse=True)


def advance_occurrence_naive(
    candidate_naive: datetime,
    start_naive: datetime,
    recurrence: str,
    *,
    reverse: bool = False,
) -> datetime:
    if recurrence == "hourly":
        return candidate_naive + timedelta(hours=-1 if reverse else 1)
    if recurrence == "daily":
        return candidate_naive + timedelta(days=-1 if reverse else 1)
    if recurrence == "weekly":
        return candidate_naive + timedelta(days=-7 if reverse else 7)
    if recurrence == "monthly":
        delta = -1 if reverse else 1
        return _month_candidate(start_naive, _month_index(candidate_naive) + delta)
    if recurrence == "yearly":
        delta = -1 if reverse else 1
        return _year_candidate(start_naive, candidate_naive.year + delta)
    raise ValidationError(f"Unsupported automation recurrence '{recurrence}'.")


def _resolve_hourly_candidate(
    start_naive: datetime,
    pivot_naive: datetime,
    *,
    inclusive: bool,
) -> datetime:
    delta_seconds = (pivot_naive - start_naive).total_seconds()
    offset_hours = max(0, int(delta_seconds // 3600))
    candidate = start_naive + timedelta(hours=offset_hours)
    if candidate < pivot_naive or (candidate == pivot_naive and not inclusive):
        candidate += timedelta(hours=1)
    return candidate


def _resolve_daily_candidate(
    start_naive: datetime,
    pivot_naive: datetime,
    *,
    inclusive: bool,
) -> datetime:
    day_diff = (pivot_naive.date() - start_naive.date()).days
    offset_days = max(0, day_diff)
    candidate = datetime.combine(
        start_naive.date() + timedelta(days=offset_days),
        start_naive.time(),
    )
    if candidate < pivot_naive or (candidate == pivot_naive and not inclusive):
        candidate += timedelta(days=1)
    return candidate


def _resolve_weekly_candidate(
    start_naive: datetime,
    pivot_naive: datetime,
    *,
    inclusive: bool,
) -> datetime:
    day_diff = (pivot_naive.date() - start_naive.date()).days
    offset_weeks = max(0, day_diff // 7)
    candidate = datetime.combine(
        start_naive.date() + timedelta(days=offset_weeks * 7),
        start_naive.time(),
    )
    if candidate < pivot_naive or (candidate == pivot_naive and not inclusive):
        candidate += timedelta(days=7)
    return candidate


def _resolve_monthly_candidate(
    start_naive: datetime,
    pivot_naive: datetime,
    *,
    inclusive: bool,
) -> datetime:
    anchor_month_index = _month_index(start_naive)
    pivot_month_index = _month_index(pivot_naive)
    offset_months = max(0, pivot_month_index - anchor_month_index)
    candidate = _month_candidate(start_naive, anchor_month_index + offset_months)
    if candidate < pivot_naive or (candidate == pivot_naive and not inclusive):
        candidate = _month_candidate(start_naive, anchor_month_index + offset_months + 1)
    return candidate


def _resolve_yearly_candidate(
    start_naive: datetime,
    pivot_naive: datetime,
    *,
    inclusive: bool,
) -> datetime:
    offset_years = max(0, pivot_naive.year - start_naive.year)
    candidate = _year_candidate(start_naive, start_naive.year + offset_years)
    if candidate < pivot_naive or (candidate == pivot_naive and not inclusive):
        candidate = _year_candidate(start_naive, start_naive.year + offset_years + 1)
    return candidate


def _month_index(value: datetime) -> int:
    return value.year * 12 + (value.month - 1)


def _month_candidate(start_naive: datetime, month_index: int) -> datetime:
    year = month_index // 12
    month = (month_index % 12) + 1
    day = min(start_naive.day, last_day_of_month(year, month))
    return datetime(
        year,
        month,
        day,
        start_naive.hour,
        start_naive.minute,
    )


def _year_candidate(start_naive: datetime, year: int) -> datetime:
    day = min(start_naive.day, last_day_of_month(year, start_naive.month))
    return datetime(
        year,
        start_naive.month,
        day,
        start_naive.hour,
        start_naive.minute,
    )
