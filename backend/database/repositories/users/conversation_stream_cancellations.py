"""SoAI - Durable Chat stream cancellation repository [backend/database/repositories/users/conversation_stream_cancellations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import JSONDict
from core.validation.strings import coerce_required_non_empty_str
from database.repositories.users.conversation_stream_cancellation_queries import (
    query_has_chat_stream_cancellation_for_input,
    query_has_chat_stream_cancellation_receipt,
    query_has_pending_chat_stream_cancellation,
)
from database.repositories.users.conversation_stream_cancellation_receipts import (
    sync_accept_chat_stream_cancellation,
    sync_settle_local_chat_stream_cancellation,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.storage_backed_repository_runtime import (
    queue_storage_backed_write,
)

if TYPE_CHECKING:
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseConversationStreamCancellations",)


class DatabaseConversationStreamCancellations:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.event_bus = deps.event_bus

    async def is_accepted(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str,
    ) -> bool:
        return await self.core.reader.execute_read(
            query_has_chat_stream_cancellation_receipt,
            int(user_id),
            coerce_required_non_empty_str(conv_id, label="conv_id"),
            coerce_required_non_empty_str(request_id, label="request_id"),
        )

    async def is_accepted_for_input(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str,
    ) -> bool:
        return await self.core.reader.execute_read(
            query_has_chat_stream_cancellation_for_input,
            int(user_id),
            coerce_required_non_empty_str(conv_id, label="conv_id"),
            coerce_required_non_empty_str(request_id, label="request_id"),
        )

    async def accept(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str,
        force_pending_steers: bool,
        allow_unpersisted_target: bool,
    ) -> JSONDict:
        result = await queue_storage_backed_write(
            self.core,
            sync_accept_chat_stream_cancellation,
            int(user_id),
            coerce_required_non_empty_str(conv_id, label="conv_id"),
            coerce_required_non_empty_str(request_id, label="request_id"),
            force_pending_steers,
            allow_unpersisted_target,
        )
        if result.get("created") is True or result.get("recovered") is True:
            notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return result

    async def has_pending(self, *, conv_id: str, user_id: int) -> bool:
        return await self.core.reader.execute_read(
            query_has_pending_chat_stream_cancellation,
            int(user_id),
            coerce_required_non_empty_str(conv_id, label="conv_id"),
        )

    async def settle_local(
        self,
        *,
        conv_id: str,
        user_id: int,
        request_id: str,
    ) -> None:
        await queue_storage_backed_write(
            self.core,
            sync_settle_local_chat_stream_cancellation,
            int(user_id),
            coerce_required_non_empty_str(conv_id, label="conv_id"),
            coerce_required_non_empty_str(request_id, label="request_id"),
        )
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
