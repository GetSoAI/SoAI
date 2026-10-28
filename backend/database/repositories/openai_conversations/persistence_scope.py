"""SoAI - OpenAI conversation persistence scope validation [backend/database/repositories/openai_conversations/persistence_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ValidationError
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.owner_scope import read_stored_owner_scope

__all__ = ("require_matching_conversation_owner",)


def _read_existing_conversation_owner(
    database: sqlite3.Connection,
    *,
    conversation_id: str,
) -> tuple[int | None, str | None] | None:
    row = sync_fetch_one_as_dict(
        database.execute(
            """
            SELECT user_id, api_key_id
            FROM openai_conversations
            WHERE conversation_id = ?
            LIMIT 1
            """,
            (conversation_id,),
        ),
    )
    if row is None:
        return None
    owner_scope = read_stored_owner_scope(
        row,
        user_id_key="user_id",
        token_id_key="api_key_id",
        error_message="Stored conversation ownership is invalid.",
    )
    return (owner_scope.user_id, owner_scope.api_key_id)


def require_matching_conversation_owner(
    database: sqlite3.Connection,
    *,
    conversation_id: str,
    user_id: int | None,
    api_key_id: str | None,
) -> None:
    existing_owner = _read_existing_conversation_owner(
        database,
        conversation_id=conversation_id,
    )
    if existing_owner is None:
        return
    existing_user_id, existing_api_key_id = existing_owner
    if existing_user_id != user_id or existing_api_key_id != api_key_id:
        raise ValidationError("Conversation ownership mismatch.")
