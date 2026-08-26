"""SoAI - Calendar recurrence expansion helpers [backend/features/calendar/calendar_occurrences.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import UTC, timedelta

from dateutil.rrule import rrulestr

from core.timing.formatting import timestamp_ms_to_utc_datetime
from core.types.json import JSONDict

__all__ = (
    "event_has_window_occurrence",
    "expand_events_for_window",
)


def expand_events_for_window(
    *,
    events: list[JSONDict],
    window_start_ms: int,
    window_end_ms: int,
    max_expansions_per_event: int,
) -> list[JSONDict]:
    expanded: list[JSONDict] = []
    for event in events:
        expanded.extend(
            _expand_event_occurrences(
                event=event,
                window_start_ms=window_start_ms,
                window_end_ms=window_end_ms,
                max_expansions_per_event=max_expansions_per_event,
            ),
        )
    return expanded


def event_has_window_occurrence(
    *,
    event: JSONDict,
    window_start_ms: int,
    window_end_ms: int,
    max_expansions_per_event: int,
) -> bool:
    return bool(
        _expand_event_occurrences(
            event=event,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
            max_expansions_per_event=max_expansions_per_event,
        ),
    )


def _expand_event_occurrences(
    *,
    event: JSONDict,
    window_start_ms: int,
    window_end_ms: int,
    max_expansions_per_event: int,
) -> list[JSONDict]:
    start_at_ms = event.get("start_at_ms")
    end_at_ms = event.get("end_at_ms")
    if not isinstance(start_at_ms, int) or not isinstance(end_at_ms, int):
        return []
    end_at_ms = max(end_at_ms, start_at_ms)
    recurrence_value = event.get("recurrence")
    recurrence = recurrence_value if isinstance(recurrence_value, dict) else None
    rrule_value = recurrence.get("rrule") if recurrence is not None else None
    rrule_text = rrule_value.strip() if isinstance(rrule_value, str) else ""
    if not rrule_text:
        return (
            [_build_occurrence_row(event, start_at_ms, end_at_ms)]
            if _overlaps_window(start_at_ms, end_at_ms, window_start_ms, window_end_ms)
            else []
        )
    duration_ms = max(end_at_ms - start_at_ms, 0)
    search_start_ms = max(window_start_ms - duration_ms, 0)
    base_start = timestamp_ms_to_utc_datetime(start_at_ms)
    search_start = timestamp_ms_to_utc_datetime(search_start_ms)
    search_end = timestamp_ms_to_utc_datetime(window_end_ms)
    try:
        occurrences = rrulestr(rrule_text, dtstart=base_start).between(
            search_start,
            search_end,
            inc=True,
        )
    except (TypeError, ValueError):
        return (
            [_build_occurrence_row(event, start_at_ms, end_at_ms)]
            if _overlaps_window(start_at_ms, end_at_ms, window_start_ms, window_end_ms)
            else []
        )
    exdates_ms = _read_exdates_ms(recurrence)
    expanded: list[JSONDict] = []
    limit = max(1, max_expansions_per_event)
    for occurrence in occurrences[:limit]:
        occurrence_start_ms = int(occurrence.astimezone(UTC).timestamp() * 1000)
        if occurrence_start_ms in exdates_ms:
            continue
        occurrence_end_ms = occurrence_start_ms + duration_ms
        if not _overlaps_window(
            occurrence_start_ms,
            occurrence_end_ms,
            window_start_ms,
            window_end_ms,
        ):
            continue
        expanded.append(_build_occurrence_row(event, occurrence_start_ms, occurrence_end_ms))
    return expanded


def _build_occurrence_row(
    event: JSONDict,
    occurrence_start_ms: int,
    occurrence_end_ms: int,
) -> JSONDict:
    occurrence = dict(event)
    occurrence["start_at_ms"] = occurrence_start_ms
    occurrence["end_at_ms"] = occurrence_end_ms
    occurrence["occurrence_start_at_ms"] = occurrence_start_ms
    occurrence["occurrence_end_at_ms"] = occurrence_end_ms
    return occurrence


def _read_exdates_ms(recurrence: JSONDict | None) -> set[int]:
    if recurrence is None:
        return set()
    exdates_value = recurrence.get("exdates_ms")
    if not isinstance(exdates_value, list):
        return set()
    return {int(entry) for entry in exdates_value if isinstance(entry, int)}


def _overlaps_window(
    start_at_ms: int,
    end_at_ms: int,
    window_start_ms: int,
    window_end_ms: int,
) -> bool:
    if end_at_ms <= start_at_ms:
        end_at_ms = start_at_ms + int(timedelta(milliseconds=1).total_seconds() * 1000)
    return start_at_ms < window_end_ms and end_at_ms > window_start_ms
