"""SoAI - Database repository for OpenAI chat completions storage [backend/database/repositories/openai_chat_completions/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from sqlite3 import Error
from typing import TYPE_CHECKING

from core.errors.exceptions import DatabaseError
from core.timing.durations import seconds_to_ms
from core.validation.strings import coerce_optional_trimmed_str
from database.core.storage_fields import resolve_deleted_at_ms
from database.repositories.openai_chat_completions.read_ops import (
    read_get_chat_completion_cursor_query,
    read_get_chat_completion_record_query,
    read_list_chat_completions_query,
)
from database.repositories.openai_chat_completions.write_ops import (
    sync_mark_chat_completion_deleted,
    sync_update_chat_completion_metadata,
    sync_upsert_chat_completion,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseOpenAIChatCompletions",)


class DatabaseOpenAIChatCompletions:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core

    async def upsert_chat_completion(
        self,
        *,
        completion_id: str,
        task_id: str,
        api_key_id: str | None,
        model: str,
        created_at_seconds: int,
        store: bool,
        request_json: JSONDict,
        completion_json: JSONDict,
        metadata_json: JSONDict,
    ) -> None:
        created_at_ms = seconds_to_ms(int(created_at_seconds))
        try:
            await self.core.writer.queue_write_operation(
                sync_upsert_chat_completion,
                completion_id,
                task_id,
                api_key_id,
                model,
                int(created_at_ms),
                bool(store),
                dict(request_json),
                dict(completion_json),
                dict(metadata_json),
            )
        except Error as exception:
            raise DatabaseError(
                "Failed to persist OpenAI chat completion.",
                operation="database.openai_chat_completions.upsert",
                cause=exception,
            ) from exception

    async def get_chat_completion_record(
        self,
        *,
        completion_id: str,
        api_key_id: str | None,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            read_get_chat_completion_record_query,
            completion_id=completion_id,
            api_key_id=api_key_id,
        )

    async def get_cursor_for_completion(
        self,
        *,
        completion_id: str,
        api_key_id: str | None,
    ) -> tuple[int, str] | None:
        return await self.core.reader.execute_read(
            read_get_chat_completion_cursor_query,
            completion_id=completion_id,
            api_key_id=api_key_id,
        )

    async def list_chat_completions(
        self,
        *,
        api_key_id: str | None,
        model: str | None,
        after: str | None,
        limit: int,
        order: str,
        metadata_filters: dict[str, str],
    ) -> tuple[tuple[JSONDict, ...], bool]:
        after_created_at_ms: int | None = None
        after_cursor_id: str | None = None
        normalized_after = coerce_optional_trimmed_str(after)
        if normalized_after is not None:
            cursor = await self.get_cursor_for_completion(
                completion_id=normalized_after,
                api_key_id=api_key_id,
            )
            if cursor is not None:
                after_created_at_ms, after_cursor_id = cursor
        return await self.core.reader.execute_read(
            read_list_chat_completions_query,
            api_key_id=api_key_id,
            model=model,
            order=order,
            limit=int(limit),
            after_created_at_ms=after_created_at_ms,
            after_completion_id=after_cursor_id,
            metadata_filters=dict(metadata_filters),
        )

    async def update_chat_completion_metadata(
        self,
        *,
        completion_id: str,
        api_key_id: str | None,
        metadata: JSONDict,
    ) -> bool:
        rowcount = await self.core.writer.queue_write_operation(
            sync_update_chat_completion_metadata,
            completion_id,
            api_key_id,
            dict(metadata),
        )
        return int(rowcount) > 0

    async def mark_chat_completion_deleted(
        self,
        *,
        completion_id: str,
        api_key_id: str | None,
        deleted_at_ms: int | None = None,
    ) -> bool:
        deleted_at_value_ms = resolve_deleted_at_ms(deleted_at_ms)
        rowcount = await self.core.writer.queue_write_operation(
            sync_mark_chat_completion_deleted,
            completion_id,
            deleted_at_value_ms,
            api_key_id,
        )
        return int(rowcount) > 0
