"""SoAI - OpenAI conversations write operations [backend/database/repositories/openai_conversations/write_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable_strict
from database.core.storage_fields import (
    normalize_optional_api_key_id,
    normalize_optional_user_id,
    require_storage_text,
)
from database.repositories.openai_conversations.persistence_scope import (
    require_matching_conversation_owner,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_create_conversation",)


def sync_create_conversation(
    database: sqlite3.Connection,
    conversation_id: str,
    created_at_ms: int,
    metadata_json: JSONDict,
    user_id: int | None,
    api_key_id: str | None,
) -> None:
    normalized_id = require_storage_text(conversation_id, field="conversation_id")
    normalized_user_id = normalize_optional_user_id(user_id)
    normalized_api_key_id = normalize_optional_api_key_id(api_key_id)
    require_matching_conversation_owner(
        database,
        conversation_id=normalized_id,
        user_id=normalized_user_id,
        api_key_id=normalized_api_key_id,
    )
    database.execute(
        """
        INSERT INTO openai_conversations(
            conversation_id, created_at_ms, metadata_json, deleted_at_ms, user_id, api_key_id
        ) VALUES (?, ?, ?, NULL, ?, ?)
        ON CONFLICT(conversation_id) DO UPDATE SET
            created_at_ms = excluded.created_at_ms,
            metadata_json = excluded.metadata_json,
            deleted_at_ms = NULL,
            user_id = excluded.user_id,
            api_key_id = excluded.api_key_id
        """,
        (
            normalized_id,
            int(created_at_ms),
            serialize_json_compact_stable_strict(metadata_json, ensure_ascii=False),
            normalized_user_id,
            normalized_api_key_id,
        ),
    )
