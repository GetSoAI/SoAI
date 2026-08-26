"""SoAI - Automation occurrence window pagination [backend/features/automation/occurrence_window_pagination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import heapq
from collections.abc import Iterator

from core.types.json import JSONDict
from features.automation.occurrence_window_bounds import (
    validate_window_pagination,
    validate_window_range,
)
from features.automation.occurrence_window_records import (
    build_run_occurrence_window_record_from_run,
    iter_scheduled_occurrence_window_records,
    resolve_run_occurrence_window_record_identity,
    resolve_run_occurrence_window_run_id,
)
from features.automation.occurrence_window_source import (
    resolve_enabled_automation_occurrence_window_source,
)

__all__ = ("paginate_occurrence_window",)


def paginate_occurrence_window(
    *,
    automations: list[JSONDict],
    runs: list[JSONDict],
    deleted_keys: set[tuple[str, int]] | None = None,
    from_utc_ms: int,
    to_utc_ms: int,
    limit: int,
    offset: int,
) -> tuple[list[JSONDict], bool, int | None]:
    validate_window_range(from_utc_ms, to_utc_ms)
    validate_window_pagination(limit, offset)

    page: list[JSONDict] = []
    unique_index = 0
    pending_key: tuple[int, str] | None = None
    pending_record: JSONDict | None = None
    has_more = False
    deleted = deleted_keys or set()
    merged_records = heapq.merge(
        *(
            _iter_automation_window_records(
                automation,
                deleted,
                from_utc_ms=from_utc_ms,
                to_utc_ms=to_utc_ms,
            )
            for automation in automations
        ),
        _iter_run_window_records(runs, deleted),
    )

    def emit_pending() -> bool:
        nonlocal unique_index
        if pending_record is None:
            return False
        unique_index += 1
        if unique_index <= offset:
            return False
        if len(page) < limit:
            page.append(pending_record)
            return False
        return True

    for scheduled_at, automation_id, _priority, _sort_token, record in merged_records:
        key = (scheduled_at, automation_id)
        if pending_key is None:
            pending_key = key
            pending_record = record
            continue
        if key == pending_key:
            pending_record = record
            continue
        if emit_pending():
            has_more = True
            break
        pending_key = key
        pending_record = record

    if not has_more and emit_pending():
        has_more = True

    next_offset = offset + len(page) if has_more else None
    return (page, has_more, next_offset)


def _iter_automation_window_records(
    automation: JSONDict,
    deleted_keys: set[tuple[str, int]],
    *,
    from_utc_ms: int,
    to_utc_ms: int,
) -> Iterator[tuple[int, str, int, str, JSONDict]]:
    source = resolve_enabled_automation_occurrence_window_source(
        automation,
        from_utc_ms=from_utc_ms,
        to_utc_ms=to_utc_ms,
        max_items=None,
    )
    if source is None:
        return iter(())
    return iter_scheduled_occurrence_window_records(source, deleted_keys)


def _iter_run_window_records(
    runs: list[JSONDict],
    deleted_keys: set[tuple[str, int]],
) -> Iterator[tuple[int, str, int, str, JSONDict]]:
    sorted_runs = sorted(
        runs,
        key=_resolve_sorted_run_key,
    )

    def _records() -> Iterator[tuple[int, str, int, str, JSONDict]]:
        for run in sorted_runs:
            run_record = build_run_occurrence_window_record_from_run(run)
            automation_id, scheduled_at = resolve_run_occurrence_window_record_identity(run_record)
            if (automation_id, scheduled_at) in deleted_keys:
                continue
            yield (
                scheduled_at,
                automation_id,
                1,
                resolve_run_occurrence_window_run_id(run_record),
                run_record,
            )

    return _records()


def _resolve_sorted_run_key(run: JSONDict) -> tuple[int, str, str]:
    run_record = build_run_occurrence_window_record_from_run(run)
    automation_id, scheduled_at_ms = resolve_run_occurrence_window_record_identity(run_record)
    run_id = resolve_run_occurrence_window_run_id(run_record)
    return (scheduled_at_ms, automation_id, run_id)
