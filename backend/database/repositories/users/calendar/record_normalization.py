"""SoAI - Calendar repository row normalization [backend/database/repositories/users/calendar/record_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from database.core.json_codec import (
    parse_optional_json_list_field,
    parse_optional_json_object_field,
)
from database.core.row_booleans import normalize_bool_field
from database.repositories.row_formatting import format_row

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "normalize_calendar_account_row",
    "normalize_calendar_event_row",
    "normalize_calendar_row",
    "normalize_reminder_row",
    "normalize_sync_window_row",
)


def normalize_calendar_account_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    formatted = format_row(row)
    if formatted is None:
        return None
    formatted["discovered_principal"] = parse_optional_json_object_field(
        formatted.get("discovered_principal_json"),
    )
    formatted.pop("discovered_principal_json", None)
    return formatted


def normalize_calendar_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    formatted = format_row(row)
    if formatted is None:
        return None
    normalize_bool_field(formatted, "read_only")
    return formatted


def normalize_calendar_event_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    formatted = format_row(row)
    if formatted is None:
        return None
    formatted["organizer"] = parse_optional_json_object_field(formatted.get("organizer_json"))
    formatted["attendees"] = parse_optional_json_list_field(formatted.get("attendees_json"))
    formatted["recurrence"] = parse_optional_json_object_field(formatted.get("recurrence_json"))
    formatted["alarms"] = parse_optional_json_list_field(formatted.get("alarms_json"))
    for key in ("organizer_json", "attendees_json", "recurrence_json", "alarms_json"):
        formatted.pop(key, None)
    normalize_bool_field(formatted, "all_day")
    normalize_bool_field(formatted, "has_alarms")
    return formatted


def normalize_sync_window_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    return format_row(row)


def normalize_reminder_row(row: Mapping[str, SQLiteValue] | None) -> JSONDict | None:
    return format_row(row)
