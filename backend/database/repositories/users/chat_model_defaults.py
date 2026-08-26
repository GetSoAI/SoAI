"""SoAI - Chat model defaults persistence per user+model [backend/database/repositories/users/chat_model_defaults.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError, ValidationError
from core.users.user_id import is_strict_user_id
from core.validation.strings import coerce_optional_trimmed_str
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_one_to_dict, sync_fetch_one_as_dict
from database.core.sqlite_numbers import coerce_int_from_sqlite

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseChatModelDefaults",)


class DatabaseChatModelDefaults:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core

    def _format_row(self, row: SQLiteRowDict | None) -> JSONDict | None:
        if not row:
            return None
        user_id = coerce_int_from_sqlite(row.get("user_id"))
        if not is_strict_user_id(user_id):
            raise StateError("Chat model defaults row has invalid user_id.")
        model_id_value = row.get("model_id")
        normalized_model_id = (
            coerce_optional_trimmed_str(model_id_value) if isinstance(model_id_value, str) else None
        )
        if normalized_model_id is None:
            raise StateError("Chat model defaults row has invalid model_id.")
        assistant_value = row.get("assistant_display_name")
        assistant_display_name = coerce_optional_trimmed_str(assistant_value)
        prompt_value = row.get("user_system_prompt")
        user_system_prompt = prompt_value if coerce_optional_trimmed_str(prompt_value) else None
        enabled_value = row.get("soai_system_prompt_enabled")
        if enabled_value in (0, 1):
            enabled = enabled_value == 1
        elif isinstance(enabled_value, bool):
            enabled = enabled_value
        else:
            enabled = True
        updated_at_ms = coerce_int_from_sqlite(row.get("updated_at_ms"))
        if updated_at_ms is None or updated_at_ms <= 0:
            raise StateError("Chat model defaults row has invalid updated_at_ms.")
        return {
            "user_id": int(user_id),
            "model_id": normalized_model_id,
            "assistant_display_name": assistant_display_name or None,
            "user_system_prompt": user_system_prompt,
            "soai_system_prompt_enabled": bool(enabled),
            "updated_at_ms": int(updated_at_ms),
        }

    def _sync_get(self, conn: sqlite3.Connection, user_id: int, model_id: str) -> JSONDict | None:
        cursor = conn.execute(
            """
            SELECT user_id, model_id, assistant_display_name, user_system_prompt, soai_system_prompt_enabled, updated_at_ms
            FROM webui_chat_model_defaults
            WHERE user_id = ? AND model_id = ?
            """,
            (user_id, model_id),
        )
        return self._format_row(sync_fetch_one_as_dict(cursor))

    async def get_model_defaults(self, user_id: int, model_id: str) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        normalized_model_id = coerce_optional_trimmed_str(model_id)
        if normalized_model_id is None:
            raise ValidationError("model_id must be a non-empty string.")

        async def _query(database: aiosqlite.Connection) -> JSONDict | None:
            row = await query_one_to_dict(
                database,
                """
                SELECT user_id, model_id, assistant_display_name, user_system_prompt, soai_system_prompt_enabled, updated_at_ms
                FROM webui_chat_model_defaults
                WHERE user_id = ? AND model_id = ?
                """,
                (user_id, normalized_model_id),
            )
            return self._format_row(row)

        return await self.core.reader.execute_read(_query)
