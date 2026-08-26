"""SoAI - Automation occurrence window merging [backend/features/automation/occurrence_window.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.automation_constants import AUTOMATION_OCCURRENCES_MAX_ITEMS
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from features.automation.occurrence_window_bounds import (
    validate_window_max_items,
    validate_window_range,
)
from features.automation.occurrence_window_records import (
    build_run_occurrence_window_record_from_run,
    iter_scheduled_occurrence_window_records,
    resolve_run_occurrence_window_record_identity,
)
from features.automation.occurrence_window_source import (
    resolve_enabled_automation_occurrence_window_source,
)

__all__ = ("merge_occurrence_window",)


def merge_occurrence_window(
    *,
    automations: list[JSONDict],
    runs: list[JSONDict],
    deleted_keys: set[tuple[str, int]] | None = None,
    from_utc_ms: int,
    to_utc_ms: int,
    max_items: int | None = AUTOMATION_OCCURRENCES_MAX_ITEMS,
) -> list[JSONDict]:
    validate_window_range(from_utc_ms, to_utc_ms)
    validate_window_max_items(max_items)
    deleted = deleted_keys or set()
    zones_by_key: dict[tuple[str, int], JSONDict] = {}
    total_items = 0
    for automation in automations:
        source = resolve_enabled_automation_occurrence_window_source(
            automation,
            from_utc_ms=from_utc_ms,
            to_utc_ms=to_utc_ms,
            max_items=max_items,
        )
        if source is None:
            continue
        for (
            scheduled_at,
            automation_id,
            _priority,
            _sort_token,
            record,
        ) in iter_scheduled_occurrence_window_records(source, deleted):
            total_items += 1
            if max_items is not None and total_items > max_items:
                raise ValidationError("Automation window exceeds the allowed occurrence limit.")
            zones_by_key[(automation_id, scheduled_at)] = record
            if max_items is not None and len(zones_by_key) > max_items:
                raise ValidationError("Automation window exceeds the allowed occurrence limit.")
    for run in runs:
        run_record = build_run_occurrence_window_record_from_run(run)
        automation_id, scheduled_at = resolve_run_occurrence_window_record_identity(run_record)
        key = (automation_id, scheduled_at)
        if key in deleted:
            continue
        is_new_zone = key not in zones_by_key
        zones_by_key[key] = run_record
        if is_new_zone and max_items is not None and len(zones_by_key) > max_items:
            raise ValidationError("Automation window exceeds the allowed occurrence limit.")
    zones = list(zones_by_key.values())
    zones.sort(key=_resolve_zone_sort_key)
    return zones


def _resolve_zone_sort_key(item: JSONDict) -> tuple[int, str]:
    automation_id, scheduled_at_ms = resolve_run_occurrence_window_record_identity(item)
    return (scheduled_at_ms, automation_id)
