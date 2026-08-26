"""SoAI - Conversation PDF export snapshot validation [backend/features/api/routes/webui/conversation_pdf_export_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from core.validation.epoch import require_unix_epoch_ms
from features.api.runtime.chat_stream_registry import (
    chat_stream_registry_slot_accepts_runtime,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from features.api.routes.webui.conversation_pdf_export_metadata import (
        ConversationPdfExportMetadata,
    )
    from features.api.runtime.context import ApiContext

__all__ = ("validate_conversation_pdf_export_snapshot",)


def _require_conversation_version(value: JSONValue | bytes) -> int:
    return require_unix_epoch_ms(
        value,
        error_message="Conversation last_modified_at_ms is invalid.",
        enforce_maximum=False,
    )


async def _require_no_active_chat_runtime(
    *,
    api_context: ApiContext,
    user_id: int,
    conversation_id: str,
) -> None:
    runtime = await api_context.dependencies.chat_stream_registry.get(
        user_id=user_id,
        conv_id=conversation_id,
    )
    if not chat_stream_registry_slot_accepts_runtime(runtime):
        raise ConflictError("Conversation is currently running and cannot be exported.")
    active_tasks = await api_context.dependencies.task_registry_queries.query_active_filtered(
        task_type=TASK_TYPE_CHAT_COMPLETION,
        owner_type="conversation",
        owner_id=conversation_id,
        limit=1,
    )
    if active_tasks:
        raise ConflictError("Conversation is currently running and cannot be exported.")


async def validate_conversation_pdf_export_snapshot(
    *,
    api_context: ApiContext,
    user_id: int,
    metadata: ConversationPdfExportMetadata,
) -> None:
    record = await api_context.dependencies.database_conversations.get_conversation(
        metadata.conversation_id,
        user_id,
    )
    if record is None:
        raise ConflictError("Conversation is no longer available for export.")
    current_version = _require_conversation_version(record.get("last_modified_at_ms"))
    if current_version != metadata.expected_last_modified_at_ms:
        raise ConflictError("Conversation has changed since the export snapshot was created.")
    record_id = record.get("id")
    if not isinstance(record_id, str) or record_id.strip() != metadata.conversation_id:
        raise StateError("Conversation access returned an unexpected conversation id.")
    await _require_no_active_chat_runtime(
        api_context=api_context,
        user_id=user_id,
        conversation_id=metadata.conversation_id,
    )
