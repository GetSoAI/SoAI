"""SoAI - Read-only automation schedule preview [backend/core/automation/automation_schedule_preview.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_constants import (
    AUTOMATION_RECURRENCE_VALUES,
    build_automation_recurrence_error_message,
)
from core.automation.automation_local_time import (
    classify_local_naive_resolution,
    format_start_local,
    local_naive_from_utc_ms,
    parse_start_local,
    require_timezone,
    resolve_local_naive_to_utc_ms,
)
from core.automation.automation_recurrence import resolve_next_run_at
from core.errors.exceptions import ValidationError
from core.timing.timezones import normalize_timezone_name

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("preview_automation_schedule",)


def preview_automation_schedule(
    *,
    timezone_name: str,
    start_local: str,
    recurrence: str,
    enabled: bool,
    now_ms: int,
) -> JSONDict:
    resolved_timezone = normalize_timezone_name(timezone_name)
    require_timezone(resolved_timezone)
    if recurrence not in AUTOMATION_RECURRENCE_VALUES:
        raise ValidationError(
            build_automation_recurrence_error_message(), details={"field": "recurrence"}
        )
    start_naive = parse_start_local(start_local)
    first_occurrence_at_ms = resolve_local_naive_to_utc_ms(start_naive, resolved_timezone)
    effective_start_local = format_start_local(
        local_naive_from_utc_ms(first_occurrence_at_ms, resolved_timezone),
    )
    start_in_past = recurrence == "none" and first_occurrence_at_ms <= now_ms
    next_occurrence_at_ms = (
        None
        if not enabled or start_in_past
        else resolve_next_run_at(
            timezone_name=resolved_timezone,
            start_local=start_local,
            recurrence=recurrence,
            enabled=True,
            now_ms=now_ms,
        )
    )
    return {
        "timezone": resolved_timezone,
        "start_local": format_start_local(start_naive),
        "effective_start_local": effective_start_local,
        "start_local_resolution": classify_local_naive_resolution(start_naive, resolved_timezone),
        "first_occurrence_at_ms": first_occurrence_at_ms,
        "next_occurrence_at_ms": next_occurrence_at_ms,
        "one_shot_start_in_past": start_in_past,
    }
