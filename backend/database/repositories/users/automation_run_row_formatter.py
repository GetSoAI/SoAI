"""SoAI - Automation run row formatter [backend/database/repositories/users/automation_run_row_formatter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.automation_run_serialization import (
    serialize_automation_run_snapshot,
)
from core.errors.exceptions import StateError
from core.types.json import JSONDict
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.automation_row_parsing import (
    decode_automation_row_json_object,
    decode_automation_row_str_list,
    parse_automation_run_shared_fields,
)

__all__ = ("format_automation_run_execution_row", "format_automation_run_row")

_LABEL_PREFIX = "Automation run field"


def _format_decoded_automation_run_row(row: SQLiteRowDict | None) -> JSONDict | None:
    if not row:
        return None
    normalized_run_record = parse_automation_run_shared_fields(
        row,
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    normalized_run_record["turns_snapshot"] = decode_automation_row_str_list(
        row,
        "turns_snapshot",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    normalized_run_record["model_settings_snapshot"] = decode_automation_row_json_object(
        row,
        "model_settings_snapshot",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    normalized_run_record["limits_snapshot"] = decode_automation_row_json_object(
        row,
        "limits_snapshot",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    return normalized_run_record


def format_automation_run_execution_row(row: SQLiteRowDict | None) -> JSONDict | None:
    return _format_decoded_automation_run_row(row)


def format_automation_run_row(row: SQLiteRowDict | None) -> JSONDict | None:
    normalized_run_record = _format_decoded_automation_run_row(row)
    if normalized_run_record is None:
        return None
    serialized_run_record = serialize_automation_run_snapshot(normalized_run_record)
    if serialized_run_record is None:
        raise StateError("Automation run row is invalid.")
    return serialized_run_record
