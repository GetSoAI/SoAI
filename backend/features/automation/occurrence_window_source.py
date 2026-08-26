"""SoAI - Automation occurrence window source helpers [backend/features/automation/occurrence_window_source.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.automation.automation_record_validation import (
    require_automation_optional_str_field,
    require_automation_str_field,
)
from core.automation.automation_recurrence import iter_occurrences_in_window
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict

__all__ = (
    "EnabledAutomationOccurrenceWindowSource",
    "resolve_enabled_automation_occurrence_window_source",
)

_LABEL_PREFIX = "Automation field"


@dataclass(frozen=True, slots=True)
class EnabledAutomationOccurrenceWindowSource:
    automation_id: str
    title: str
    color: str | None
    occurrences: list[int]


def resolve_enabled_automation_occurrence_window_source(
    automation: JSONDict,
    *,
    from_utc_ms: int,
    to_utc_ms: int,
    max_items: int | None,
) -> EnabledAutomationOccurrenceWindowSource | None:
    if automation.get("enabled") is not True:
        return None
    automation_id = require_automation_str_field(
        automation,
        "id",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )
    title = require_automation_str_field(
        automation,
        "title",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )
    timezone_name = require_automation_str_field(
        automation,
        "timezone",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )
    start_local = require_automation_str_field(
        automation,
        "start_local",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )
    recurrence = require_automation_str_field(
        automation,
        "recurrence",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )
    color = require_automation_optional_str_field(
        automation,
        "color",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )
    occurrences = iter_occurrences_in_window(
        timezone_name=timezone_name,
        start_local=start_local,
        recurrence=recurrence,
        from_utc_ms=from_utc_ms,
        to_utc_ms=to_utc_ms,
        max_items=max_items,
    )
    return EnabledAutomationOccurrenceWindowSource(
        automation_id=automation_id,
        title=title,
        color=color,
        occurrences=occurrences,
    )
