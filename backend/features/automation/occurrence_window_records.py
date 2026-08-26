"""SoAI - Automation occurrence window records [backend/features/automation/occurrence_window_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterator

from core.automation.automation_record_validation import (
    require_automation_int_field,
    require_automation_optional_bool_field,
    require_automation_optional_int_field,
    require_automation_optional_str_field,
    require_automation_str_field,
)
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from features.automation.occurrence_window_source import (
    EnabledAutomationOccurrenceWindowSource,
)

__all__ = (
    "build_run_occurrence_window_record",
    "build_run_occurrence_window_record_from_run",
    "build_scheduled_occurrence_window_record",
    "iter_scheduled_occurrence_window_records",
    "resolve_run_occurrence_window_record_identity",
    "resolve_run_occurrence_window_run_id",
)

_LABEL_PREFIX = "Automation field"


def build_scheduled_occurrence_window_record(
    *,
    automation_id: str,
    scheduled_at_ms: int,
    title: str,
    color: str | None,
) -> JSONDict:
    return {
        "automation_id": automation_id,
        "scheduled_at_ms": scheduled_at_ms,
        "title": title,
        "enabled": True,
        "run_id": None,
        "status": "scheduled",
        "status_message": None,
        "result_excerpt": None,
        "conv_id": None,
        "started_at_actual_ms": None,
        "finished_at_ms": None,
        "color": color,
    }


def build_run_occurrence_window_record(
    *,
    automation_id: str,
    scheduled_at_ms: int,
    title: str,
    enabled: bool | None,
    run_id: str | None,
    status: str,
    status_message: str | None,
    result_excerpt: str | None,
    conv_id: str | None,
    started_at_actual_ms: int | None,
    finished_at_ms: int | None,
    color: str | None,
) -> JSONDict:
    return {
        "automation_id": automation_id,
        "scheduled_at_ms": scheduled_at_ms,
        "title": title,
        "enabled": enabled,
        "run_id": run_id,
        "status": status,
        "status_message": status_message,
        "result_excerpt": result_excerpt,
        "conv_id": conv_id,
        "started_at_actual_ms": started_at_actual_ms,
        "finished_at_ms": finished_at_ms,
        "color": color,
    }


def build_run_occurrence_window_record_from_run(run: JSONDict) -> JSONDict:
    automation_id = require_automation_str_field(
        run,
        "automation_id",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )
    scheduled_at_ms = require_automation_int_field(
        run,
        "scheduled_at_ms",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )
    title = (
        require_automation_optional_str_field(
            run,
            "title",
            build_error=ValidationError,
            label_prefix=_LABEL_PREFIX,
        )
        or automation_id
    )
    return build_run_occurrence_window_record(
        automation_id=automation_id,
        scheduled_at_ms=scheduled_at_ms,
        title=title,
        enabled=require_automation_optional_bool_field(
            run,
            "enabled",
            build_error=ValidationError,
            label_prefix=_LABEL_PREFIX,
        ),
        run_id=require_automation_optional_str_field(
            run,
            "run_id",
            build_error=ValidationError,
            label_prefix=_LABEL_PREFIX,
        ),
        status=require_automation_str_field(
            run,
            "status",
            build_error=ValidationError,
            label_prefix=_LABEL_PREFIX,
        ),
        status_message=require_automation_optional_str_field(
            run,
            "status_message",
            build_error=ValidationError,
            label_prefix=_LABEL_PREFIX,
        ),
        result_excerpt=require_automation_optional_str_field(
            run,
            "result_excerpt",
            build_error=ValidationError,
            label_prefix=_LABEL_PREFIX,
        ),
        conv_id=require_automation_optional_str_field(
            run,
            "conv_id",
            build_error=ValidationError,
            label_prefix=_LABEL_PREFIX,
        ),
        started_at_actual_ms=require_automation_optional_int_field(
            run,
            "started_at_actual_ms",
            build_error=ValidationError,
            label_prefix=_LABEL_PREFIX,
        ),
        finished_at_ms=require_automation_optional_int_field(
            run,
            "finished_at_ms",
            build_error=ValidationError,
            label_prefix=_LABEL_PREFIX,
        ),
        color=require_automation_optional_str_field(
            run,
            "color",
            build_error=ValidationError,
            label_prefix=_LABEL_PREFIX,
        ),
    )


def resolve_run_occurrence_window_record_identity(
    run_record: JSONDict,
) -> tuple[str, int]:
    automation_id = require_automation_str_field(
        run_record,
        "automation_id",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )
    scheduled_at_ms = require_automation_int_field(
        run_record,
        "scheduled_at_ms",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )
    return (automation_id, scheduled_at_ms)


def resolve_run_occurrence_window_run_id(run_record: JSONDict) -> str:
    return require_automation_str_field(
        run_record,
        "run_id",
        build_error=ValidationError,
        label_prefix=_LABEL_PREFIX,
    )


def iter_scheduled_occurrence_window_records(
    source: EnabledAutomationOccurrenceWindowSource,
    deleted_keys: set[tuple[str, int]],
) -> Iterator[tuple[int, str, int, str, JSONDict]]:
    for scheduled_at in source.occurrences:
        if (source.automation_id, scheduled_at) in deleted_keys:
            continue
        yield (
            scheduled_at,
            source.automation_id,
            0,
            source.automation_id,
            build_scheduled_occurrence_window_record(
                automation_id=source.automation_id,
                scheduled_at_ms=scheduled_at,
                title=source.title,
                color=source.color,
            ),
        )
