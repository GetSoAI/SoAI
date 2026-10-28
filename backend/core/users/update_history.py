"""SoAI - Concurrent user update history merging [backend/core/users/update_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import copy_json_dict, require_json_dict
from core.validation.strict_numbers import require_int_in_range_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("merge_update_history_preferences",)

_UPDATE_HISTORY_KEYS = ("soai_updates_application_history", "soai_updates_system_history")
_HISTORY_FIELDS = frozenset(
    {"schemaVersion", "checkedAtMs", "resultAtMs", "result", "failure", "updatedAtMs"}
)


@dataclass(frozen=True, slots=True)
class _UpdateHistoryRecord:
    checked_at_ms: int | None
    result_at_ms: int | None
    result: JSONDict | None
    failure: str | None
    updated_at_ms: int | None

    def to_json(self) -> JSONDict:
        return {
            "schemaVersion": 1,
            "checkedAtMs": self.checked_at_ms,
            "resultAtMs": self.result_at_ms,
            "result": copy_json_dict(self.result) if self.result is not None else None,
            "failure": self.failure,
            "updatedAtMs": self.updated_at_ms,
        }


def _read_timestamp(record: JSONDict, field: str) -> int | None:
    value = record[field]
    if value is None:
        return None
    return require_int_in_range_strict(
        value,
        minimum=0,
        maximum=9_007_199_254_740_991,
        error_message=f"Update history {field} must be a non-negative safe integer.",
    )


def _read_history(value: JSONValue) -> _UpdateHistoryRecord:
    record = require_json_dict(value, label="Update history")
    if set(record) != _HISTORY_FIELDS:
        raise ValidationError("Update history has an unsupported format. Reload SoAI and retry.")
    require_int_in_range_strict(
        record["schemaVersion"],
        minimum=1,
        maximum=1,
        error_message="Update history has an unsupported version. Reload SoAI and retry.",
    )
    result_value = record["result"]
    result = (
        None if result_value is None else require_json_dict(result_value, label="Update result")
    )
    failure = record["failure"]
    if failure is not None and (not isinstance(failure, str) or not failure.strip()):
        raise ValidationError("Update history failure must be non-empty text or null.")
    checked_at_ms = _read_timestamp(record, "checkedAtMs")
    result_at_ms = _read_timestamp(record, "resultAtMs")
    if (result is None) != (result_at_ms is None) or (
        result_at_ms is not None and (checked_at_ms is None or result_at_ms > checked_at_ms)
    ):
        raise ValidationError("Update history result timestamps are inconsistent. Retry the check.")
    if failure is not None and checked_at_ms is None:
        raise ValidationError("Update history failure requires a check timestamp.")
    return _UpdateHistoryRecord(
        checked_at_ms=checked_at_ms,
        result_at_ms=result_at_ms,
        result=result,
        failure=failure,
        updated_at_ms=_read_timestamp(record, "updatedAtMs"),
    )


def _newer_timestamp(current: int | None, incoming: int | None) -> bool:
    return incoming is not None and (current is None or incoming > current)


def _merge_history(current: _UpdateHistoryRecord, incoming: _UpdateHistoryRecord) -> JSONDict:
    conflicting_result = (
        incoming.result_at_ms is not None
        and incoming.result_at_ms == current.result_at_ms
        and incoming.result != current.result
    )
    conflicting_check = (
        incoming.checked_at_ms is not None
        and incoming.checked_at_ms == current.checked_at_ms
        and incoming.failure != current.failure
    )
    if conflicting_result or conflicting_check:
        raise ValidationError("Update history records conflict. Retry the update check.")
    check = incoming if _newer_timestamp(current.checked_at_ms, incoming.checked_at_ms) else current
    result = incoming if _newer_timestamp(current.result_at_ms, incoming.result_at_ms) else current
    updated_at_ms = (
        incoming.updated_at_ms
        if _newer_timestamp(current.updated_at_ms, incoming.updated_at_ms)
        else current.updated_at_ms
    )
    return _UpdateHistoryRecord(
        checked_at_ms=check.checked_at_ms,
        result_at_ms=result.result_at_ms,
        result=result.result,
        failure=check.failure,
        updated_at_ms=updated_at_ms,
    ).to_json()


def merge_update_history_preferences(current: JSONDict, patch: JSONDict, merged: JSONDict) -> None:
    incoming_misc = patch.get("misc")
    if not isinstance(incoming_misc, dict):
        return
    current_misc = current.get("misc")
    merged_misc = require_json_dict(merged.get("misc"), label="User preferences misc")
    for key in _UPDATE_HISTORY_KEYS:
        if key not in incoming_misc:
            continue
        incoming = _read_history(incoming_misc[key])
        if isinstance(current_misc, dict) and key in current_misc:
            merged_misc[key] = _merge_history(_read_history(current_misc[key]), incoming)
        else:
            merged_misc[key] = incoming.to_json()
    merged["misc"] = merged_misc
