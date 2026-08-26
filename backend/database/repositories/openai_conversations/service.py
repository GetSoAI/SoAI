"""SoAI - Database repository for OpenAI Conversations storage [backend/database/repositories/openai_conversations/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.openai_conversations.read_ops import (
    read_get_conversation_query,
    read_list_items_query,
)
from database.repositories.openai_conversations.write_ops import (
    sync_create_conversation,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseOpenAIConversations",)


class DatabaseOpenAIConversations:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core

    async def create_conversation(
        self,
        *,
        conversation_id: str,
        created_at_ms: int,
        metadata_json: JSONDict,
        user_id: int | None,
        api_key_id: str | None,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_create_conversation,
            conversation_id,
            int(created_at_ms),
            dict(metadata_json),
            user_id,
            api_key_id,
        )

    async def get_conversation(
        self,
        *,
        conversation_id: str,
        user_id: int | None,
        api_key_id: str | None,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            read_get_conversation_query,
            conversation_id=conversation_id,
            user_id=user_id,
            api_key_id=api_key_id,
        )

    async def list_items(
        self,
        *,
        conversation_id: str,
        user_id: int | None,
        api_key_id: str | None,
        limit: int,
        order: str,
        after: str | None,
        before: str | None,
    ) -> tuple[tuple[JSONDict, ...], bool]:
        return await self.core.reader.execute_read(
            read_list_items_query,
            conversation_id=conversation_id,
            user_id=user_id,
            api_key_id=api_key_id,
            limit=int(limit),
            order=order,
            after=after,
            before=before,
        )
