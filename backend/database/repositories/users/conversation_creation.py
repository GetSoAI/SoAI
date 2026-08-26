"""SoAI - Canonical conversation creation transaction [backend/database/repositories/users/conversation_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.openai.model_settings_validation import validate_model_settings
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.conversation_row_formatter import (
    format_conversation_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_create_conversation",)


def sync_create_conversation(
    conn: sqlite3.Connection,
    user_id: int,
    title: str,
    model_settings: JSONDict,
    is_automation: bool,
    conv_id: str | None = None,
    *,
    messaging_platform: str | None = None,
    messaging_account_label: str | None = None,
    messaging_account_snapshot_id: str | None = None,
) -> JSONDict:
    resolved_conv_id = conv_id or f"conv_{uuid.uuid4().hex}"
    now_ms = epoch_ms()
    validated_settings = validate_model_settings(model_settings)
    settings_json = serialize_json_compact_stable_strict(validated_settings)
    is_messaging = messaging_platform is not None
    if is_automation and is_messaging:
        raise ValidationError("A conversation cannot be both Automation and Messaging.")
    if is_messaging and (
        not isinstance(messaging_account_label, str)
        or not messaging_account_label.strip()
        or not isinstance(messaging_account_snapshot_id, str)
        or not messaging_account_snapshot_id.strip()
    ):
        raise ValidationError("Messaging conversation identity is incomplete.")
    try:
        conn.execute(
            """
            INSERT INTO webui_conversations (
                id, user_id, title, created_at_ms, last_modified_at_ms, model_settings,
                is_automation, is_messaging, messaging_platform,
                messaging_account_label, messaging_account_snapshot_id, is_archived
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_conv_id,
                user_id,
                title,
                now_ms,
                now_ms,
                settings_json,
                1 if is_automation else 0,
                1 if is_messaging else 0,
                messaging_platform,
                messaging_account_label,
                messaging_account_snapshot_id,
                0,
            ),
        )
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type in ("unique", "primary_key"):
            raise ConflictError(
                f"Conversation with ID '{resolved_conv_id}' already exists.",
            ) from exception
        if constraint_type == "foreign_key":
            raise ValidationError(f"User with ID '{user_id}' does not exist.") from exception
        if constraint_type == "check":
            raise ValidationError(
                f"Invalid conversation data: constraint violation on {detail or 'unknown field'}.",
            ) from exception
        raise StateError(f"Database constraint violation: {exception}") from exception
    result = format_conversation_row(
        {
            "id": resolved_conv_id,
            "user_id": user_id,
            "title": title,
            "created_at_ms": now_ms,
            "last_modified_at_ms": now_ms,
            "model_settings": settings_json,
            "color": None,
            "is_favorite": 0,
            "is_automation": 1 if is_automation else 0,
            "is_messaging": 1 if is_messaging else 0,
            "messaging_platform": messaging_platform,
            "messaging_account_label": messaging_account_label,
            "messaging_account_snapshot_id": messaging_account_snapshot_id,
            "is_archived": 0,
            "compaction_count": 0,
            "compaction_tokens_saved": 0,
            "input_generation": 0,
        },
    )
    if result is None:
        raise StateError("Failed to format new conversation.")
    return result
