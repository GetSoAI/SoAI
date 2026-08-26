"""SoAI - Atomic conversation settings and defaults commit [backend/database/repositories/users/conversation_settings_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.settings_commit import ConversationSettingsCommitResult
from core.errors.exceptions import StateError
from core.openai.model_settings_validation import validate_model_settings
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from database.repositories.users.conversation_event_outbox import (
    sync_enqueue_conversation_updated_event,
)
from database.repositories.users.conversation_sync_operations import sync_get_conversation
from database.repositories.users.conversation_versioning import NEXT_LAST_MODIFIED_SQL
from database.repositories.users.user_preference_mutations import (
    sync_replace_conversation_defaults_model_settings,
)

__all__ = ("sync_commit_conversation_settings",)


def _defaults_snapshot(settings: JSONDict) -> JSONDict:
    sanitized = dict(settings)
    sanitized.pop("workspace_path", None)
    return sanitized


def _require_last_modified_at_ms(conversation: JSONDict) -> int:
    value = conversation.get("last_modified_at_ms")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise StateError("Committed conversation has invalid last_modified_at_ms.")
    return value


def sync_commit_conversation_settings(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    new_settings: JSONDict,
) -> ConversationSettingsCommitResult | None:
    validated_settings = validate_model_settings(new_settings)
    existing = sync_get_conversation(conn, conv_id, user_id)
    if existing is None:
        return None
    existing_settings = validate_model_settings(existing.get("model_settings"))
    conversation_changed = existing_settings != validated_settings
    update_time = int(epoch_ms())
    if conversation_changed:
        updated = conn.execute(
            f"""UPDATE webui_conversations
                SET model_settings = ?, last_modified_at_ms = {NEXT_LAST_MODIFIED_SQL}
                WHERE id = ? AND user_id = ?""",
            (
                serialize_json_compact_stable_strict(validated_settings),
                update_time,
                update_time,
                conv_id,
                user_id,
            ),
        ).rowcount
        if updated != 1:
            raise StateError("Conversation disappeared during settings commit.")
    preferences = sync_replace_conversation_defaults_model_settings(
        conn,
        user_id,
        _defaults_snapshot(validated_settings),
    )
    if preferences is None:
        raise StateError("Conversation owner disappeared during settings commit.")
    authoritative = sync_get_conversation(conn, conv_id, user_id)
    if authoritative is None:
        raise StateError("Conversation disappeared after settings commit.")
    if conversation_changed:
        sync_enqueue_conversation_updated_event(
            conn,
            created_at_ms=update_time,
            user_id=user_id,
            conv_id=conv_id,
            last_modified_at_ms=_require_last_modified_at_ms(authoritative),
            model_settings=validated_settings,
        )
    return ConversationSettingsCommitResult(
        conversation=authoritative,
        conversation_changed=conversation_changed,
    )
