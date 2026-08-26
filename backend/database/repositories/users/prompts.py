"""SoAI - Database prompt template repository [backend/database/repositories/users/prompts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

import aiosqlite

from core.prompts.colors import validate_prompt_color
from core.timing.epoch import epoch_ms
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import (
    query_one_to_dict,
    query_to_dicts,
    sync_fetch_one_as_dict,
)
from database.repositories.users.prompt_record_codec import (
    format_prompt_row,
    normalize_prompt_content,
    prepare_prompt_record,
)
from database.repositories.users.prompt_title_search import search_prompt_titles

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabasePrompts",)


class DatabasePrompts:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    def _sync_get_prompt(
        self,
        conn: sqlite3.Connection,
        prompt_id: str,
        user_id: int,
    ) -> JSONDict | None:
        cursor = conn.execute(
            "SELECT id, user_id, name, content, color, created_at_ms, modified_at_ms FROM webui_prompts WHERE id = ? AND user_id = ?",
            (prompt_id, user_id),
        )
        return format_prompt_row(sync_fetch_one_as_dict(cursor))

    async def get_prompt(self, prompt_id: str, user_id: int) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

        async def _query(
            database: aiosqlite.Connection,
        ) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                "SELECT id, user_id, name, content, color, created_at_ms, modified_at_ms FROM webui_prompts WHERE id = ? AND user_id = ?",
                (prompt_id, user_id),
            )
            return format_prompt_row(row)

        return await self.core.reader.execute_read(_query)

    def _sync_create_prompt(
        self,
        conn: sqlite3.Connection,
        user_id: int,
        name: str,
        content: str,
        color: str | None,
    ) -> JSONDict:
        prompt_id = uuid.uuid4().hex
        now = epoch_ms()
        sanitized_name, sanitized_content, sanitized_color = prepare_prompt_record(
            name,
            content,
            color,
        )
        conn.execute(
            "INSERT INTO webui_prompts (id, user_id, name, content, color, created_at_ms, modified_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                prompt_id,
                user_id,
                sanitized_name,
                sanitized_content,
                sanitized_color,
                now,
                now,
            ),
        )
        return {
            "id": prompt_id,
            "user_id": user_id,
            "name": sanitized_name,
            "content": sanitized_content,
            "color": sanitized_color,
            "created_at_ms": now,
            "modified_at_ms": now,
        }

    async def create_prompt(
        self,
        user_id: int,
        name: str,
        content: str,
        color: str | None = None,
    ) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            self._sync_create_prompt,
            user_id,
            name,
            content,
            color,
        )

    async def list_prompts(self, user_id: int, color: str | None = None) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        sanitized_color = validate_prompt_color(color)

        async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
            if sanitized_color:
                rows = await query_to_dicts(
                    database,
                    "SELECT id, user_id, name, content, color, created_at_ms, modified_at_ms FROM webui_prompts WHERE user_id = ? AND color = ? ORDER BY modified_at_ms DESC",
                    (user_id, sanitized_color),
                )
            else:
                rows = await query_to_dicts(
                    database,
                    "SELECT id, user_id, name, content, color, created_at_ms, modified_at_ms FROM webui_prompts WHERE user_id = ? ORDER BY modified_at_ms DESC",
                    (user_id,),
                )
            return [formatted for row in rows if row and (formatted := format_prompt_row(row))]

        prompts = await self.core.reader.execute_read(_query)
        return prompts

    async def search_prompt_titles(self, user_id: int, query: str, limit: int) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await search_prompt_titles(
            self.core,
            user_id=user_id,
            query=query,
            limit=limit,
        )

    def _sync_update_prompt(
        self,
        conn: sqlite3.Connection,
        prompt_id: str,
        user_id: int,
        name: str,
        content: str,
        color: str | None,
    ) -> JSONDict | None:
        current = self._sync_get_prompt(conn, prompt_id, user_id)
        if not current:
            return None
        sanitized_name, sanitized_content, sanitized_color = prepare_prompt_record(
            name,
            content,
            color,
        )
        name_changed = sanitized_name != current["name"]
        content_changed = sanitized_content != normalize_prompt_content(current["content"])
        color_changed = sanitized_color != current["color"]
        if not (name_changed or content_changed or color_changed):
            return current
        if name_changed or content_changed:
            now = epoch_ms()
            updated = conn.execute(
                "UPDATE webui_prompts SET name = ?, content = ?, color = ?, modified_at_ms = ? WHERE id = ? AND user_id = ?",
                (
                    sanitized_name,
                    sanitized_content,
                    sanitized_color,
                    now,
                    prompt_id,
                    user_id,
                ),
            ).rowcount
        else:
            updated = conn.execute(
                "UPDATE webui_prompts SET color = ? WHERE id = ? AND user_id = ?",
                (sanitized_color, prompt_id, user_id),
            ).rowcount
        if updated == 0:
            return None
        return self._sync_get_prompt(conn, prompt_id, user_id)

    async def update_prompt(
        self,
        prompt_id: str,
        user_id: int,
        name: str,
        content: str,
        color: str | None = None,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            self._sync_update_prompt,
            prompt_id,
            user_id,
            name,
            content,
            color,
        )

    def _sync_delete_prompt(self, conn: sqlite3.Connection, prompt_id: str, user_id: int) -> bool:
        return (
            conn.execute(
                "DELETE FROM webui_prompts WHERE id = ? AND user_id = ?",
                (prompt_id, user_id),
            ).rowcount
            > 0
        )

    async def delete_prompt(self, prompt_id: str, user_id: int) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            self._sync_delete_prompt,
            prompt_id,
            user_id,
        )

    def _sync_delete_prompts_batch(
        self,
        conn: sqlite3.Connection,
        prompt_ids: list[str],
        user_id: int,
    ) -> int:
        ids = [str(pid).strip() for pid in dict.fromkeys(prompt_ids) if pid and str(pid).strip()]
        if not ids:
            return 0
        deleted = 0
        for start_index in range(0, len(ids), SQLITE_BATCH_SIZE):
            batch = ids[start_index : start_index + SQLITE_BATCH_SIZE]
            placeholders = ",".join("?" for _ in batch)
            deleted += conn.execute(
                f"DELETE FROM webui_prompts WHERE user_id = ? AND id IN ({placeholders})",
                (user_id, *batch),
            ).rowcount
        return deleted

    async def delete_prompts_batch(self, prompt_ids: list[str], user_id: int) -> int:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            self._sync_delete_prompts_batch,
            prompt_ids,
            user_id,
        )
