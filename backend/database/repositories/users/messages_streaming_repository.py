"""SoAI - Streaming message repository persistence [backend/database/repositories/users/messages_streaming_repository.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
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
from database.repositories.users.message_streaming_assistant.message_finalization_transactions import (
    sync_finalize_streaming_assistant_message,
)
from database.repositories.users.message_streaming_assistant.message_transactions import (
    sync_append_streaming_assistant_placeholder,
    sync_delete_streaming_assistant_message,
    sync_update_streaming_assistant_content,
)

if TYPE_CHECKING:
    from core.conversations.conversation_input_finalization import (
        ConversationInputFinalization,
    )
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

    async def finalize_streaming_assistant_message(
        self: DatabaseDomainEventOwnerProtocol,
        conv_id: str,
        user_id: int,
        *,
        created_at_ms: int,
        request_id: str | None,
        finish_reason: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
        usage_source: str | None,
        generation_latency_ms: int | None,
        thinking_tail_duration_ms: int | None,
        terminal_reason: str | None = None,
        input_finalization: ConversationInputFinalization | None = None,
        input_terminal_code: str | None = None,
    ) -> ConversationMessageWriteResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        result = await self.core.writer.queue_write_operation(
            sync_finalize_streaming_assistant_message,
            conv_id,
            user_id,
            created_at_ms,
            request_id,
            finish_reason,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            usage_source,
            generation_latency_ms,
            thinking_tail_duration_ms,
            terminal_reason,
            input_finalization,
            input_terminal_code,
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
