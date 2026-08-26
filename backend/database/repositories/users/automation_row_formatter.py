"""SoAI - Automation row validation and formatting [backend/database/repositories/users/automation_row_formatter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.automation_interactive_tool_approval import (
    extract_interactive_tool_approval,
    strip_interactive_tool_approval,
)
from core.automation.automation_record_validation import (
    require_automation_epoch_field,
    require_automation_int_field,
    require_automation_optional_color_field,
    require_automation_optional_epoch_field,
    require_automation_str_field,
)
from core.errors.exceptions import StateError
from core.openai.model_settings_validation import validate_model_settings
from core.types.json import JSONDict
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.automation_row_parsing import (
    decode_automation_row_bool,
    decode_automation_row_json_object,
    decode_automation_row_str_list,
)

__all__ = (
    "format_automation_row",
    "format_automation_window_source_row",
)

_LABEL_PREFIX = "Automation field"


def format_automation_row(row: SQLiteRowDict | None) -> JSONDict | None:
    if not row:
        return None
    automation_id = require_automation_str_field(
        row,
        "id",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    title = require_automation_str_field(
        row,
        "title",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    timezone_value = require_automation_str_field(
        row,
        "timezone",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    start_local = require_automation_str_field(
        row,
        "start_local",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    recurrence = require_automation_str_field(
        row,
        "recurrence",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    color = require_automation_optional_color_field(
        row,
        "color",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    turns = decode_automation_row_str_list(
        row,
        "turns",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    model_settings = validate_model_settings(
        decode_automation_row_json_object(
            row,
            "model_settings",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
    )
    interactive_tool_approval = extract_interactive_tool_approval(model_settings)
    public_model_settings = strip_interactive_tool_approval(model_settings)
    return {
        "id": automation_id,
        "user_id": require_automation_int_field(
            row,
            "user_id",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
            minimum=1,
        ),
        "title": title,
        "enabled": decode_automation_row_bool(
            row,
            "enabled",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        "color": color,
        "timezone": timezone_value,
        "start_local": start_local,
        "recurrence": recurrence,
        "next_run_at_ms": require_automation_optional_epoch_field(
            row,
            "next_run_at_ms",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        "interactive_tool_approval": interactive_tool_approval,
        "model_settings": public_model_settings,
        "turns": turns,
        "max_turns": require_automation_int_field(
            row,
            "max_turns",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
            minimum=1,
        ),
        "max_turn_chars": require_automation_int_field(
            row,
            "max_turn_chars",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
            minimum=1,
        ),
        "max_run_minutes": require_automation_int_field(
            row,
            "max_run_minutes",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
            minimum=1,
        ),
        "created_at_ms": require_automation_epoch_field(
            row,
            "created_at_ms",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        "last_modified_at_ms": require_automation_epoch_field(
            row,
            "last_modified_at_ms",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
    }


def format_automation_window_source_row(row: SQLiteRowDict | None) -> JSONDict | None:
    if not row:
        return None
    automation_id = require_automation_str_field(
        row,
        "id",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    title = require_automation_str_field(
        row,
        "title",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    timezone_value = require_automation_str_field(
        row,
        "timezone",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    start_local = require_automation_str_field(
        row,
        "start_local",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    recurrence = require_automation_str_field(
        row,
        "recurrence",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    color = require_automation_optional_color_field(
        row,
        "color",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    return {
        "id": automation_id,
        "title": title,
        "enabled": True,
        "timezone": timezone_value,
        "start_local": start_local,
        "recurrence": recurrence,
        "color": color,
    }
