"""SoAI - Interval and aggregation normalization utilities [backend/core/history/intervals.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    type IntervalRaw = int | float | str

__all__ = (
    "normalize_aggregations",
    "normalize_history_intervals_and_aggregations",
    "normalize_tracked_metrics",
    "sanitize_supported_intervals",
)

DEFAULT_HISTORY_INTERVALS_MS: tuple[int, ...] = (
    3_000,
    60_000,
    120_000,
    300_000,
    600_000,
    900_000,
    1_800_000,
    3_600_000,
    7_200_000,
    21_600_000,
    43_200_000,
    86_400_000,
)


def sanitize_supported_intervals(
    intervals: Iterable[IntervalRaw] | None,
    base_interval: IntervalRaw | None,
    extra_defaults: tuple[IntervalRaw, ...] | None = None,
    allow_empty: bool = True,
) -> list[int]:
    sources: list[IntervalRaw] = []
    if intervals is not None:
        sources.extend(intervals)
    if base_interval is not None:
        sources.append(base_interval)
    if extra_defaults:
        sources.extend(extra_defaults)
    candidates: set[int] = set()
    for raw in sources:
        if not isinstance(raw, int | float | str):
            continue
        try:
            numeric = int(float(raw))
            if numeric > 0:
                candidates.add(numeric)
        except (OverflowError, TypeError, ValueError):
            continue
    sanitized = sorted(candidates)
    if sanitized or allow_empty:
        return sanitized
    raise ValidationError("No valid positive intervals supplied.")


def normalize_aggregations(
    values: Iterable[str] | None,
    mandatory: tuple[str, ...] | None = None,
) -> list[str]:
    sources: list[str] = []
    if values is not None:
        sources.extend(values)
    if mandatory:
        sources.extend(mandatory)
    normalized: list[str] = []
    seen: set[str] = set()
    for value in sources:
        if not isinstance(value, str):
            continue
        lowered = value.strip().lower()
        if not lowered or lowered in seen:
            continue
        normalized.append(lowered)
        seen.add(lowered)
    return normalized


def normalize_history_intervals_and_aggregations(
    raw_intervals: Iterable[IntervalRaw] | None,
    base_interval: IntervalRaw | None,
    extra_defaults: tuple[IntervalRaw, ...],
    allow_empty_intervals: bool,
    raw_aggregations: Iterable[str] | None,
    default_aggregations: Iterable[str],
    mandatory_aggregations: Collection[str],
) -> tuple[list[int], list[str]]:
    sanitized_intervals = sanitize_supported_intervals(
        raw_intervals,
        base_interval,
        extra_defaults=extra_defaults,
        allow_empty=allow_empty_intervals,
    )
    aggregation_candidates: list[str] = []
    aggregation_candidates.extend(default_aggregations)
    if raw_aggregations is not None:
        aggregation_candidates.extend(raw_aggregations)
    normalized_aggs = normalize_aggregations(
        aggregation_candidates,
        mandatory=tuple(str(aggregation_value) for aggregation_value in mandatory_aggregations),
    )
    if not normalized_aggs and mandatory_aggregations:
        normalized_aggs = [
            str(aggregation_value).strip().lower()
            for aggregation_value in mandatory_aggregations
            if isinstance(aggregation_value, str)
        ]
    return (sanitized_intervals, normalized_aggs)


def normalize_tracked_metrics(
    raw_metrics: Iterable[str] | None,
    default_metrics: Iterable[str],
) -> list[str]:
    candidates: list[str] = []
    if raw_metrics is not None:
        candidates.extend(raw_metrics)
    candidates.extend(default_metrics)
    normalized: list[str] = []
    seen: set[str] = set()
    for metric in candidates:
        lowered = metric.strip()
        if not lowered or lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(lowered)
    return normalized
