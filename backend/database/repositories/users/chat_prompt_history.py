"""SoAI - Durable per-user chat prompt history [backend/database/repositories/users/chat_prompt_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.conversations.conversation_draft_content_validation import (
    CHAT_COMPOSER_TEXT_MAX_LENGTH,
)
from core.conversations.protocols_database_chat_prompt_history import (
    CHAT_PROMPT_HISTORY_LIMIT,
)
from core.errors.exceptions import ConflictError, StateError
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.validation.strings import require_bounded_trimmed_text
from database.core.query_execution import query_to_dicts, sync_fetch_one_as_dict

if TYPE_CHECKING:
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = (
    "DatabaseChatPromptHistory",
    "build_chat_prompt_history_fingerprint",
    "sync_record_chat_prompt",
    "sync_verify_chat_prompt_replay",
)


def _require_prompt_text(value: str) -> str:
    return require_bounded_trimmed_text(
        value,
        type_message="Prompt history text must be a string.",
        empty_message="Prompt history text must be non-empty.",
        max_length=CHAT_COMPOSER_TEXT_MAX_LENGTH,
        max_length_message="Prompt history text exceeds the maximum length.",
    )


def build_chat_prompt_history_fingerprint(text: str) -> str:
    normalized_text = _require_prompt_text(text)
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def sync_record_chat_prompt(
    sqlite_conn: sqlite3.Connection,
    *,
    user_id: int,
    source_input_id: str,
    text: str,
    accepted_at_ms: int,
) -> None:
    normalized_text = _require_prompt_text(text)
    sqlite_conn.execute(
        """
        INSERT INTO webui_chat_prompt_history (
            user_id, source_input_id, text, accepted_at_ms
        ) VALUES (?, ?, ?, ?)
        """,
        (user_id, source_input_id, normalized_text, accepted_at_ms),
    )
    sqlite_conn.execute(
        """
        DELETE FROM webui_chat_prompt_history
        WHERE user_id = ? AND id NOT IN (
            SELECT id FROM webui_chat_prompt_history
            WHERE user_id = ? ORDER BY id DESC LIMIT ?
        )
        """,
        (user_id, user_id, CHAT_PROMPT_HISTORY_LIMIT),
    )


def sync_verify_chat_prompt_replay(
    sqlite_conn: sqlite3.Connection,
    *,
    source_input_id: str,
    expected_text: str | None,
    stored_fingerprint: str | None,
) -> None:
    canonical_stored_fingerprint = (
        None
        if stored_fingerprint is None
        else require_canonical_sha256_hexdigest(
            stored_fingerprint,
            label="Conversation input prompt history fingerprint",
        )
    )
    expected_fingerprint = (
        None if expected_text is None else build_chat_prompt_history_fingerprint(expected_text)
    )
    if canonical_stored_fingerprint != expected_fingerprint:
        raise ConflictError("Conversation input prompt history conflict.")
    row = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            "SELECT text FROM webui_chat_prompt_history WHERE source_input_id = ? LIMIT 1",
            (source_input_id,),
        ),
    )
    if row is None:
        return
    history_text = row.get("text")
    if not isinstance(history_text, str) or canonical_stored_fingerprint is None:
        raise StateError("Conversation input prompt history metadata is inconsistent.")
    history_fingerprint = build_chat_prompt_history_fingerprint(history_text)
    if history_fingerprint != canonical_stored_fingerprint:
        raise StateError("Conversation input prompt history metadata is inconsistent.")


def _sync_clear_chat_prompt_history(
    sqlite_conn: sqlite3.Connection,
    user_id: int,
) -> None:
    sqlite_conn.execute(
        "DELETE FROM webui_chat_prompt_history WHERE user_id = ?",
        (user_id,),
    )


class DatabaseChatPromptHistory:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    async def list_prompts(self, *, user_id: int) -> list[str]:
        async def query(database: aiosqlite.Connection) -> list[str]:
            rows = await query_to_dicts(
                database,
                """
                SELECT text FROM webui_chat_prompt_history
                WHERE user_id = ? ORDER BY id DESC LIMIT ?
                """,
                (user_id, CHAT_PROMPT_HISTORY_LIMIT),
            )
            prompts: list[str] = []
            for row in rows:
                text = row.get("text")
                if not isinstance(text, str):
                    raise StateError("Chat prompt history text is invalid.")
                prompts.append(_require_prompt_text(text))
            return prompts

        return await self.core.reader.execute_read(query)

    async def clear(self, *, user_id: int) -> None:
        await self.core.writer.queue_write_operation(
            _sync_clear_chat_prompt_history,
            user_id,
        )
