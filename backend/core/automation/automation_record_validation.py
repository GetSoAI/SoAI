"""SoAI - Shared automation record validation rules [backend/core/automation/automation_record_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from core.automation.automation_constants import AUTOMATION_RUN_STATUS_VALUES
from core.prompts.colors import validate_prompt_color
from core.validation.epoch import EPOCH_MS_MIN
from core.validation.record_fields import (
    require_bool,
    require_int,
    require_json_list,
    require_json_object,
    require_non_empty_str,
    require_optional_bool,
    require_optional_int,
    require_optional_str,
    require_str_list,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

    type ErrorBuilder = Callable[[str], Exception]

__all__ = (
    "read_automation_requested_model",
    "require_automation_bool_field",
    "require_automation_epoch_field",
    "require_automation_int_field",
    "require_automation_json_list_field",
    "require_automation_json_object_field",
    "require_automation_optional_bool_field",
    "require_automation_optional_color_field",
    "require_automation_optional_epoch_field",
    "require_automation_optional_int_field",
    "require_automation_optional_str_field",
    "require_automation_run_status_field",
    "require_automation_str_field",
    "require_automation_str_list_field",
)


def _field_label(field_name: str, *, label_prefix: str) -> str:
    return f"{label_prefix} '{field_name}'"


def require_automation_str_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> str:
    return require_non_empty_str(
        record.get(field_name),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
    )


def require_automation_optional_str_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> str | None:
    return require_optional_str(
        record.get(field_name),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
    )


def require_automation_int_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
    minimum: int | None = None,
) -> int:
    return require_int(
        record.get(field_name),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
        minimum=minimum,
    )


def require_automation_optional_int_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
    minimum: int | None = None,
) -> int | None:
    return require_optional_int(
        record.get(field_name),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
        minimum=minimum,
    )


def require_automation_bool_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> bool:
    return require_bool(
        record.get(field_name),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
    )


def require_automation_optional_bool_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> bool | None:
    return require_optional_bool(
        record.get(field_name),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
    )


def require_automation_epoch_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> int:
    return require_automation_int_field(
        record,
        field_name,
        build_error=build_error,
        label_prefix=label_prefix,
        minimum=EPOCH_MS_MIN,
    )


def require_automation_optional_epoch_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> int | None:
    return require_automation_optional_int_field(
        record,
        field_name,
        build_error=build_error,
        label_prefix=label_prefix,
        minimum=EPOCH_MS_MIN,
    )


def require_automation_json_object_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> JSONDict:
    return require_json_object(
        record.get(field_name),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
    )


def require_automation_json_list_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> list[JSONValue]:
    return require_json_list(
        record.get(field_name),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
    )


def require_automation_str_list_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> list[str]:
    return require_str_list(
        record.get(field_name),
        label=_field_label(field_name, label_prefix=label_prefix),
        build_error=build_error,
    )


def require_automation_optional_color_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> str | None:
    value = require_automation_optional_str_field(
        record,
        field_name,
        build_error=build_error,
        label_prefix=label_prefix,
    )
    if value is None:
        return None
    return validate_prompt_color(value)


def require_automation_run_status_field(
    record: Mapping[str, JSONValue],
    field_name: str,
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
) -> str:
    status = require_automation_str_field(
        record,
        field_name,
        build_error=build_error,
        label_prefix=label_prefix,
    )
    if status not in AUTOMATION_RUN_STATUS_VALUES:
        raise build_error(f"{_field_label(field_name, label_prefix=label_prefix)} is invalid.")
    return status


def read_automation_requested_model(
    record: Mapping[str, JSONValue],
    *,
    build_error: ErrorBuilder,
    label_prefix: str,
    field_name: str = "model_settings_snapshot",
) -> str | None:
    model_settings_snapshot = require_automation_json_object_field(
        record,
        field_name,
        build_error=build_error,
        label_prefix=label_prefix,
    )
    model_value = model_settings_snapshot.get("model")
    if model_value is None:
        return None
    if not isinstance(model_value, str):
        raise build_error(f"{_field_label(field_name, label_prefix=label_prefix)} is invalid.")
    normalized = model_value.strip()
    return normalized or None
