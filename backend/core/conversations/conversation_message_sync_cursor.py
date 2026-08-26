"""SoAI - Conversation message sync cursor model [backend/core/conversations/conversation_message_sync_cursor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("ConversationMessageSyncCursor",)


@dataclass(frozen=True, slots=True)
class ConversationMessageSyncCursor:
    latest_timestamp: int | None
    last_modified_at_ms: int
    message_count: int
