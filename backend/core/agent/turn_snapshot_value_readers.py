"""SoAI - Agent turn snapshot primitive and JSON readers [backend/core/agent/turn_snapshot_value_readers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import is_json_dict, is_json_list, is_json_value
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "read_json_object_list",
    "read_json_value_list",
    "read_optional_int",
    "read_optional_json_dict",
    "read_optional_str",
    "read_optional_text",
    "read_required_bool",
    "read_required_int",
    "read_required_str",
)


def read_required_str(turn_record: JSONDict, field_name: str) -> str | None:
    value = turn_record.get(field_name)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def read_optional_str(turn_record: JSONDict, field_name: str) -> str | None:
    value = turn_record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def read_optional_text(turn_record: JSONDict, field_name: str) -> str | None:
    value = turn_record.get(field_name)
    if value is None:
        return None
    return value if isinstance(value, str) else None


def read_required_int(
    turn_record: JSONDict,
    field_name: str,
    *,
    minimum: int,
) -> int | None:
    value = turn_record.get(field_name)
    if not is_strict_int(value) or value < minimum:
        return None
    return value


def read_optional_int(
    turn_record: JSONDict,
    field_name: str,
    *,
    minimum: int,
) -> int | None:
    value = turn_record.get(field_name)
    if value is None:
        return None
    if not is_strict_int(value) or value < minimum:
        return None
    return value


def read_required_bool(turn_record: JSONDict, field_name: str) -> bool | None:
    value = turn_record.get(field_name)
    return value if isinstance(value, bool) else None


def read_json_object_list(value: JSONValue) -> list[JSONDict] | None:
    if not is_json_list(value):
        return None
    normalized_items: list[JSONDict] = []
    for item in value:
        normalized = coerce_json_dict(item)
        if normalized is None:
            return None
        normalized_items.append(normalized)
    return normalized_items


def read_json_value_list(value: JSONValue) -> list[JSONValue] | None:
    if not is_json_list(value):
        return None
    normalized_items: list[JSONValue] = []
    for item in value:
        if not is_json_value(item):
            return None
        normalized_items.append(item)
    return normalized_items


def read_optional_json_dict(
    turn_record: JSONDict,
    field_name: str,
) -> JSONDict | None:
    value = turn_record.get(field_name)
    if value is None:
        return None
    if not is_json_dict(value):
        return None
    return dict(value)
