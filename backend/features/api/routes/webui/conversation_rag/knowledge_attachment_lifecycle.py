"""SoAI - WebUI RAG knowledge attachment lifecycle [backend/features/api/routes/webui/conversation_rag/knowledge_attachment_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_constants import STAGED_ATTACHMENT_TTL_MS
from core.timing.epoch import epoch_ms
from core.validation.strings import coerce_optional_trimmed_str
from features.api.routes.webui.conversation_attachments.events import (
    publish_knowledge_attachment_changed,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("ensure_and_publish_knowledge_attachment",)


async def ensure_and_publish_knowledge_attachment(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    source_type: str,
    operation_type: str,
    title: str,
    root_label: str | None = None,
    root_virtual_path: str | None = None,
    task_id: str | None = None,
    client_batch_id: str | None = None,
    created_at_ms: int | None = None,
) -> JSONDict:
    created_at = created_at_ms if created_at_ms is not None else epoch_ms()
    summary = await api_context.dependencies.database_conversation_knowledge_attachments.ensure_knowledge_attachment(
        conv_id=conv_id,
        user_id=user_id,
        source_type=source_type,
        operation_type=operation_type,
        title=coerce_optional_trimmed_str(title) or "Knowledge update",
        root_label=coerce_optional_trimmed_str(root_label),
        root_virtual_path=coerce_optional_trimmed_str(root_virtual_path),
        task_id=coerce_optional_trimmed_str(task_id),
        client_batch_id=coerce_optional_trimmed_str(client_batch_id),
        created_at_ms=created_at,
        expires_at_ms=created_at + STAGED_ATTACHMENT_TTL_MS,
    )
    await publish_knowledge_attachment_changed(api_context.dependencies.event_bus, summary=summary)
    return summary
