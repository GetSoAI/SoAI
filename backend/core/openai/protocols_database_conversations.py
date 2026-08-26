"""SoAI - OpenAI Conversations database protocol contract [backend/core/openai/protocols_database_conversations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("DatabaseOpenAIConversationsProtocol",)


class DatabaseOpenAIConversationsProtocol(Protocol):
    async def create_conversation(
        self,
        *,
        conversation_id: str,
        created_at_ms: int,
        metadata_json: JSONDict,
        user_id: int | None,
        api_key_id: str | None,
    ) -> None: ...

    async def get_conversation(
        self,
        *,
        conversation_id: str,
        user_id: int | None,
        api_key_id: str | None,
    ) -> JSONDict | None: ...

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
    ) -> tuple[tuple[JSONDict, ...], bool]: ...
