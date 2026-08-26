"""SoAI - Conversation row validation and formatting [backend/database/repositories/users/conversation_row_formatter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.conversation_source import build_conversation_source_metadata
from core.conversations.settings_authority import (
    build_settings_authority_payload,
    resolve_conversation_settings_authority,
)
from core.errors.exceptions import StateError
from core.openai.model_settings_validation import validate_model_settings
from core.prompts.colors import validate_prompt_color
from core.validation.strings import coerce_optional_trimmed_str
from database.core.row_fields import (
    require_row_bool,
    require_row_epoch_ms,
    require_row_non_empty_str,
    require_row_non_negative_int,
    require_row_positive_int,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("attach_conversation_settings_authority", "format_conversation_row")


def attach_conversation_settings_authority(formatted: JSONDict) -> JSONDict:
    formatted["settings_authority"] = build_settings_authority_payload(
        resolve_conversation_settings_authority(formatted),
    )
    return formatted


def format_conversation_row(row: SQLiteRowDict | None) -> JSONDict | None:
    if not row:
        return None
    formatted: JSONDict = {}
    formatted["id"] = require_row_non_empty_str(
        row.get("id"),
        label="Conversation id",
        build_error=StateError,
    )
    formatted["user_id"] = require_row_positive_int(
        row.get("user_id"),
        label="Conversation user_id",
        build_error=StateError,
    )
    formatted["created_at_ms"] = require_row_epoch_ms(
        row.get("created_at_ms"),
        label="Conversation created_at_ms",
        build_error=StateError,
    )
    formatted["last_modified_at_ms"] = require_row_epoch_ms(
        row.get("last_modified_at_ms"),
        label="Conversation last_modified_at_ms",
        build_error=StateError,
    )
    formatted["message_count"] = require_row_non_negative_int(
        row.get("message_count") or 0,
        label="Conversation message_count",
        build_error=StateError,
    )
    formatted["title"] = require_row_non_empty_str(
        row.get("title"),
        label="Conversation title",
        build_error=StateError,
    )
    model_settings_value = row.get("model_settings")
    if model_settings_value is None:
        raise StateError("Conversation model_settings is missing or invalid.")
    if isinstance(model_settings_value, str) and not model_settings_value.strip():
        raise StateError("Conversation model_settings is missing or invalid.")
    formatted["model_settings"] = validate_model_settings(model_settings_value)
    color_value = row.get("color")
    if color_value is None:
        formatted["color"] = None
    elif isinstance(color_value, str):
        if not color_value.strip():
            raise StateError("Conversation color is invalid.")
        formatted["color"] = validate_prompt_color(color_value)
    else:
        raise StateError("Conversation color is invalid.")
    formatted["is_favorite"] = require_row_bool(
        row.get("is_favorite"),
        label="Conversation is_favorite",
        build_error=StateError,
    )
    formatted["is_automation"] = require_row_bool(
        row.get("is_automation"),
        label="Conversation is_automation",
        build_error=StateError,
    )
    _format_messaging_source(row, formatted)
    formatted["is_archived"] = require_row_bool(
        row.get("is_archived"),
        label="Conversation is_archived",
        build_error=StateError,
    )
    formatted["compaction_count"] = require_row_non_negative_int(
        row.get("compaction_count") or 0,
        label="Conversation compaction_count",
        build_error=StateError,
    )
    formatted["compaction_tokens_saved"] = require_row_non_negative_int(
        row.get("compaction_tokens_saved") or 0,
        label="Conversation compaction_tokens_saved",
        build_error=StateError,
    )
    formatted["input_generation"] = require_row_non_negative_int(
        row.get("input_generation"),
        label="Conversation input_generation",
        build_error=StateError,
    )
    return formatted


def _format_messaging_source(row: SQLiteRowDict, formatted: JSONDict) -> None:
    is_messaging = require_row_bool(
        row.get("is_messaging"),
        label="Conversation is_messaging",
        build_error=StateError,
    )
    historical_platform = coerce_optional_trimmed_str(row.get("messaging_platform"))
    historical_label = coerce_optional_trimmed_str(row.get("messaging_account_label"))
    snapshot_id = coerce_optional_trimmed_str(row.get("messaging_account_snapshot_id"))
    source = build_conversation_source_metadata(
        is_messaging=is_messaging,
        messaging_platform=historical_platform,
        messaging_account_label=historical_label,
        messaging_account_snapshot_id=snapshot_id,
    )
    live_account_id = coerce_optional_trimmed_str(row.get("messaging_account_id"))
    live_account_label = coerce_optional_trimmed_str(row.get("messaging_live_account_label"))
    live_settings_value = row.get("messaging_account_model_settings")
    if live_account_id is None:
        if live_account_label is not None or live_settings_value is not None:
            raise StateError("Messaging conversation live authority is incomplete.")
    else:
        if not source.is_messaging or live_account_label is None or live_settings_value is None:
            raise StateError("Messaging conversation live authority is incomplete.")
        formatted["messaging_account_model_settings"] = validate_model_settings(
            live_settings_value,
        )
    formatted.update(source.to_payload())
    formatted["messaging_account_label"] = live_account_label or historical_label
    formatted["messaging_account_id"] = live_account_id
