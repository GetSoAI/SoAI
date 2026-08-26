"""SoAI - Message append ordering validation [backend/database/repositories/users/message_append_order_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.conversation_message_storage_types import (
    ConversationMessageStoragePayload,
)
from core.errors.exceptions import ConflictError
from core.validation.epoch import require_unix_epoch_ms

__all__ = ("sync_require_append_timestamps_after_existing",)


def _load_latest_existing_timestamp(conn: sqlite3.Connection, conv_id: str) -> int | None:
    row = conn.execute(
        "SELECT created_at_ms FROM webui_messages WHERE conv_id = ? ORDER BY created_at_ms DESC, id DESC LIMIT 1",
        (conv_id,),
    ).fetchone()
    if row is None:
        return None
    timestamp_value = row[0]
    if timestamp_value is None:
        return None
    return require_unix_epoch_ms(
        timestamp_value,
        error_message=(
            "Stored conversation message created_at_ms must be an epoch-millisecond integer for append validation."
        ),
        enforce_maximum=False,
    )


def sync_require_append_timestamps_after_existing(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    validated_messages: list[ConversationMessageStoragePayload],
) -> None:
    latest_existing_timestamp = _load_latest_existing_timestamp(conn, conv_id)
    if not validated_messages or latest_existing_timestamp is None:
        return
    first_new_timestamp = validated_messages[0].get("created_at_ms")
    if isinstance(first_new_timestamp, int) and first_new_timestamp <= latest_existing_timestamp:
        raise ConflictError(
            "Appended message created_at_ms values must be strictly greater than existing conversation message created_at_ms values.",
        )
