"""SoAI - Database repository for OpenAI Responses storage [backend/database/repositories/openai_responses/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.timing.durations import seconds_to_ms
from core.timing.epoch import epoch_ms
from database.repositories.openai_item_ids import ensure_item_ids
from database.repositories.openai_responses.background_task_finalization import (
    sync_reconcile_terminal_background_response,
)
from database.repositories.openai_responses.compaction_crypto import (
    decrypt_compaction_content,
    encrypt_compaction_content,
)
from database.repositories.openai_responses.read_ops import (
    read_get_response_query,
    read_get_response_record_query,
    read_list_events_after_query,
)
from database.repositories.openai_responses.read_ops_input_items import (
    read_list_input_items_query,
)
from database.repositories.openai_responses.write_ops import (
    sync_upsert_response_artifacts,
)
from database.repositories.openai_responses.write_ops_response_rows import (
    sync_delete_response,
)
from database.repositories.openai_responses.write_ops_status_and_event import (
    sync_append_nonterminal_response_event,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseOpenAIResponses",)


class DatabaseOpenAIResponses:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core
        self.config = deps.config
        self._fernet = deps.fernet

    async def upsert_response_artifacts(
        self,
        *,
        response_id: str,
        task_id: str,
        user_id: int | None,
        api_key_id: str | None,
        model: str,
        created_at_seconds: int,
        status: str,
        store: bool,
        is_background: bool,
        stream_enabled: bool,
        response_json: JSONDict,
        input_items: Sequence[JSONDict] | None,
        input_items_created_at_ms: int,
        event_payloads: Sequence[JSONDict],
        event_sequence_start: int,
        reset_events: bool,
        create_if_missing: bool,
        event_created_at_ms: int | None = None,
    ) -> bool:
        normalized_items = tuple(ensure_item_ids(input_items)) if input_items is not None else None
        normalized_payloads = tuple(
            dict(payload) for payload in event_payloads if isinstance(payload, dict)
        )
        created_at_ms = seconds_to_ms(int(created_at_seconds))
        return await self.core.writer.queue_write_operation(
            sync_upsert_response_artifacts,
            response_id,
            task_id,
            user_id,
            api_key_id,
            model,
            int(created_at_ms),
            status,
            bool(store),
            bool(is_background),
            bool(stream_enabled),
            dict(response_json),
            normalized_items,
            int(input_items_created_at_ms),
            normalized_payloads,
            int(event_sequence_start),
            bool(reset_events),
            bool(create_if_missing),
            int(epoch_ms() if event_created_at_ms is None else event_created_at_ms),
        )

    async def delete_response(
        self,
        *,
        response_id: str,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> bool:
        rowcount = await self.core.writer.queue_write_operation(
            sync_delete_response,
            response_id,
            user_id,
            api_key_id,
        )
        return int(rowcount) > 0

    async def append_nonterminal_response_event(
        self,
        *,
        response_id: str,
        response_json: JSONDict,
        event_json: JSONDict,
        event_created_at_ms: int,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> int | None:
        return await self.core.writer.queue_write_operation(
            sync_append_nonterminal_response_event,
            response_id,
            response_json,
            event_json,
            int(event_created_at_ms),
            user_id,
            api_key_id,
        )

    async def reconcile_terminal_background_response(self, *, task_id: str) -> int:
        return await self.core.writer.queue_write_operation(
            sync_reconcile_terminal_background_response,
            task_id,
        )

    async def get_response(
        self,
        *,
        response_id: str,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            read_get_response_query,
            response_id=response_id,
            user_id=user_id,
            api_key_id=api_key_id,
        )

    async def get_response_record(
        self,
        *,
        response_id: str,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            read_get_response_record_query,
            response_id=response_id,
            user_id=user_id,
            api_key_id=api_key_id,
        )

    async def list_input_items(
        self,
        *,
        response_id: str,
        limit: int,
        order: str,
        after: str | None,
        before: str | None,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> JSONDict:
        return await self.core.reader.execute_read(
            read_list_input_items_query,
            response_id=response_id,
            limit=int(limit),
            order=order,
            after=after,
            before=before,
            user_id=user_id,
            api_key_id=api_key_id,
        )

    async def list_events_after(
        self,
        *,
        response_id: str,
        starting_after: int,
        limit: int,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> tuple[tuple[JSONDict, ...], bool]:
        return await self.core.reader.execute_read(
            read_list_events_after_query,
            response_id=response_id,
            starting_after=int(starting_after),
            limit=int(limit),
            user_id=user_id,
            api_key_id=api_key_id,
        )

    def encrypt_compaction_content(self, *, content: JSONDict) -> str:
        return encrypt_compaction_content(fernet_chain=self._fernet, content=content)

    def decrypt_compaction_content(self, *, encrypted_content: str) -> JSONDict:
        return decrypt_compaction_content(
            fernet_chain=self._fernet,
            encrypted_content=encrypted_content,
        )
