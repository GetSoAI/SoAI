"""SoAI - Streaming message repository persistence [backend/database/repositories/users/messages_streaming_repository.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
)
from core.conversations.streaming_assistant_terminal_commit import (
    StreamingAssistantTerminalCommitRequest,
)
from core.database.protocols import DatabaseCoreProtocol
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict
from database.core.flags import FEATURE_PROMPTS
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.internal_protocols import (
    DatabaseDomainEventOwnerProtocol,
    DatabaseMessagesCoreOwnerProtocol,
)
from database.repositories.users.message_streaming_assistant.event_transactions import (
    sync_append_streaming_assistant_events_batch,
    sync_delete_streaming_assistant_events,
)
from database.repositories.users.message_streaming_assistant.message_transactions import (
    sync_append_streaming_assistant_placeholder,
    sync_delete_streaming_assistant_message,
    sync_update_streaming_assistant_content,
)
from database.repositories.users.message_streaming_assistant.terminal_commit_transactions import (
    sync_commit_streaming_assistant_terminal,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol

__all__ = ("DatabaseMessageStreamingRepository",)


class DatabaseMessageStreamingRepository:
    if not TYPE_CHECKING:
        core: DatabaseCoreProtocol
        event_bus: EventBusProtocol | None

    async def append_streaming_assistant_placeholder(
        self: DatabaseMessagesCoreOwnerProtocol,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        assistant_turn_at_ms: int,
        request_id: str | None,
        model_id: str | None,
        model_variant_index: int,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_append_streaming_assistant_placeholder,
            conv_id,
            user_id,
            created_at_ms,
            assistant_turn_at_ms,
            request_id,
            model_id,
            model_variant_index,
        )

    async def update_streaming_assistant_content(
        self: DatabaseMessagesCoreOwnerProtocol,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        content_text: str,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_update_streaming_assistant_content,
            conv_id,
            user_id,
            created_at_ms,
            content_text,
        )

    async def append_streaming_assistant_events_batch(
        self: DatabaseMessagesCoreOwnerProtocol,
        conv_id: str,
        user_id: int,
        *,
        assistant_at_ms: int,
        events: list[tuple[int, int, str, JSONDict, int]],
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        serialized: list[tuple[int, int, str, str, int]] = []
        for sequence, assistant_revision, event_type, payload, created_at_ms in events:
            serialized.append(
                (
                    sequence,
                    assistant_revision,
                    event_type,
                    serialize_json_compact_stable_strict(payload),
                    created_at_ms,
                ),
            )
        return await self.core.writer.queue_write_operation(
            sync_append_streaming_assistant_events_batch,
            conv_id,
            user_id,
            assistant_at_ms,
            serialized,
        )

    async def commit_streaming_assistant_terminal(
        self: DatabaseDomainEventOwnerProtocol,
        request: StreamingAssistantTerminalCommitRequest,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        serialized_events = tuple(
            (
                sequence,
                assistant_revision,
                event_type,
                serialize_json_compact_stable_strict(payload),
                created_at_ms,
            )
            for sequence, assistant_revision, event_type, payload, created_at_ms in request.events
        )
        result = await self.core.writer.queue_write_operation(
            sync_commit_streaming_assistant_terminal,
            request,
            serialized_events,
        )
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return result

    async def delete_streaming_assistant_events(
        self: DatabaseMessagesCoreOwnerProtocol,
        conv_id: str,
        user_id: int,
        *,
        assistant_at_ms: int,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_delete_streaming_assistant_events,
            conv_id,
            user_id,
            assistant_at_ms,
        )

    async def delete_streaming_assistant_message(
        self: DatabaseMessagesCoreOwnerProtocol,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_delete_streaming_assistant_message,
            conv_id,
            user_id,
            created_at_ms,
        )
