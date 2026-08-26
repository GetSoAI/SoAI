"""SoAI - Chat identity defaults persistence per user [backend/database/repositories/users/chat_identity_defaults.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from core.users.user_id import is_strict_user_id
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_one_to_dict, sync_fetch_one_as_dict
from database.core.sqlite_numbers import coerce_int_from_sqlite

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseChatIdentityDefaults",)


class DatabaseChatIdentityDefaults:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    def _format_row(self, row: SQLiteRowDict | None) -> JSONDict | None:
        if not row:
            return None
        user_id = coerce_int_from_sqlite(row.get("user_id"))
        if not is_strict_user_id(user_id):
            raise StateError("Chat identity defaults row has invalid user_id.")
        value = row.get("user_display_name")
        user_display_name = value.strip() if isinstance(value, str) else None
        updated_at_ms = coerce_int_from_sqlite(row.get("updated_at_ms"))
        if updated_at_ms is None or updated_at_ms <= 0:
            raise StateError("Chat identity defaults row has invalid updated_at_ms.")
        return {
            "user_id": int(user_id),
            "user_display_name": user_display_name or None,
            "updated_at_ms": int(updated_at_ms),
        }

    def _sync_upsert_user_display_name(
        self,
        conn: sqlite3.Connection,
        user_id: int,
        user_display_name: str | None,
    ) -> None:
        now = epoch_ms()
        conn.execute(
            """
            INSERT INTO webui_chat_identity_defaults (user_id, user_display_name, updated_at_ms)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET user_display_name = excluded.user_display_name, updated_at_ms = excluded.updated_at_ms
            """,
            (user_id, user_display_name, now),
        )

    async def upsert_user_display_name(self, user_id: int, user_display_name: str | None) -> None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        normalized = user_display_name.strip() if isinstance(user_display_name, str) else None
        await self.core.writer.queue_write_operation(
            self._sync_upsert_user_display_name,
            user_id,
            normalized or None,
        )

    def _sync_get(self, conn: sqlite3.Connection, user_id: int) -> JSONDict | None:
        cursor = conn.execute(
            "SELECT user_id, user_display_name, updated_at_ms FROM webui_chat_identity_defaults WHERE user_id = ?",
            (user_id,),
        )
        return self._format_row(sync_fetch_one_as_dict(cursor))

    async def get_identity_defaults(self, user_id: int) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

        async def _query(database: aiosqlite.Connection) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                "SELECT user_id, user_display_name, updated_at_ms FROM webui_chat_identity_defaults WHERE user_id = ?",
                (user_id,),
            )
            return self._format_row(row)

        return await self.core.reader.execute_read(_query)
