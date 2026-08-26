"""SoAI - Automation repository row parsing rules [backend/database/repositories/users/automation_row_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.automation.automation_record_validation import (
    require_automation_epoch_field,
    require_automation_int_field,
    require_automation_optional_color_field,
    require_automation_optional_epoch_field,
    require_automation_optional_str_field,
    require_automation_run_status_field,
    require_automation_str_field,
)
from core.errors.exceptions import ValidationError
from core.validation.record_fields import (
    require_bool,
    require_json_object,
    require_str_list,
)
from database.core.json_codec import safe_json_deserialize

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRowDict

    type ErrorBuilder = Callable[[str], Exception]

__all__ = (
    "decode_automation_row_bool",
    "decode_automation_row_json_object",
    "decode_automation_row_json_value",
    "decode_automation_row_optional_bool",
    "decode_automation_row_str_list",
    "parse_automation_run_shared_fields",
)


def _field_label(field_name: str, *, label_prefix: str) -> str:
    return f"{label_prefix} '{field_name}'"


def decode_automation_row_json_value(
    row: SQLiteRowDict,
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> JSONValue:
    try:
        decoded = safe_json_deserialize(row.get(field_name), None)
    except ValidationError as exception:
        raise build_error(
            f"{_field_label(field_name, label_prefix=label_prefix)} is invalid.",
        ) from exception
    if decoded is None:
        raise build_error(f"{_field_label(field_name, label_prefix=label_prefix)} is invalid.")
    return decoded


def decode_automation_row_json_object(
    row: SQLiteRowDict,
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> JSONDict:
    return require_json_object(
        decode_automation_row_json_value(
            row,
            field_name,
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
    )


def decode_automation_row_str_list(
    row: SQLiteRowDict,
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> list[str]:
    return require_str_list(
        decode_automation_row_json_value(
            row,
            field_name,
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
    )


def decode_automation_row_optional_bool(
    row: SQLiteRowDict,
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> bool | None:
    value = row.get(field_name)
    if value is None:
        return None
    if isinstance(value, int) and value in (0, 1):
        return value == 1
    return require_bool(
        value,
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
    )


def decode_automation_row_bool(
    row: SQLiteRowDict,
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> bool:
    value = decode_automation_row_optional_bool(
        row,
        field_name,
        build_error=build_error,
        label_prefix=label_prefix,
    )
    if value is None:
        raise build_error(f"{_field_label(field_name, label_prefix=label_prefix)} is invalid.")
    return value


def parse_automation_run_shared_fields(
    row: SQLiteRowDict,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> JSONDict:
    return {
        "run_id": require_automation_str_field(
            row,
            "run_id",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "automation_id": require_automation_str_field(
            row,
            "automation_id",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "user_id": require_automation_int_field(
            row,
            "user_id",
            build_error=build_error,
            label_prefix=label_prefix,
            minimum=1,
        ),
        "owner_task_id": require_automation_optional_str_field(
            row,
            "owner_task_id",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "scheduled_at_ms": require_automation_epoch_field(
            row,
            "scheduled_at_ms",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "started_at_actual_ms": require_automation_optional_epoch_field(
            row,
            "started_at_actual_ms",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "finished_at_ms": require_automation_optional_epoch_field(
            row,
            "finished_at_ms",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "status": require_automation_run_status_field(
            row,
            "status",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "status_message": require_automation_optional_str_field(
            row,
            "status_message",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "conv_id": require_automation_optional_str_field(
            row,
            "conv_id",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "result_excerpt": require_automation_optional_str_field(
            row,
            "result_excerpt",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "title": require_automation_optional_str_field(
            row,
            "title",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "enabled": decode_automation_row_optional_bool(
            row,
            "enabled",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
        "color": require_automation_optional_color_field(
            row,
            "color",
            build_error=build_error,
            label_prefix=label_prefix,
        ),
    }
