"""SoAI - Manual compaction assistant event persistence helpers [backend/database/repositories/users/manual_compaction_assistant_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable_strict
from database.repositories.users.message_assistant_event_sync import (
    sync_append_streaming_assistant_event_row,
)

if TYPE_CHECKING:
    from core.database.requests import ManualCompactionAssistantEventRequest
    from core.types.json import JSONDict

__all__ = ("sync_append_manual_compaction_assistant_event",)


def sync_append_manual_compaction_assistant_event(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
    event: ManualCompactionAssistantEventRequest,
    tool_payload: JSONDict,
    created_at_ms: int,
) -> None:
    payload: JSONDict = {
        "assistant_at_ms": int(assistant_at_ms),
        "assistant_revision": int(event.assistant_revision),
        "tool": tool_payload,
    }
    sync_append_streaming_assistant_event_row(
        conn,
        conv_id=conv_id,
        assistant_at_ms=int(assistant_at_ms),
        sequence=int(event.sequence),
        assistant_revision=int(event.assistant_revision),
        event_type=str(event.event_type),
        payload_json=serialize_json_compact_stable_strict(payload),
        created_at_ms=int(created_at_ms),
    )
