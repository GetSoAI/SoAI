"""SoAI - Conversation draft route event publishing [backend/features/api/routes/webui/conversation_draft_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_system import ConversationDraftChangedEvent
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from features.api.runtime.context import ApiContext

__all__ = ("publish_conversation_draft_changed",)

LOGGER_NAME = "SoAI.features.api.conversation_draft_events"
OPERATION_CONVERSATION_DRAFT_PUBLISH = "webui.conversation_draft.publish_changed"


async def publish_conversation_draft_changed(
    *,
    api_context: ApiContext,
    user_id: int,
    conv_id: str,
    client_id: str,
    updated_at_ms: int,
    deleted: bool,
    revision: int,
) -> None:
    try:
        await api_context.dependencies.event_bus.publish(
            ConversationDraftChangedEvent(
                user_id=user_id,
                conv_id=conv_id,
                client_id=client_id,
                updated_at_ms=updated_at_ms,
                deleted=deleted,
                revision=revision,
            ),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_CONVERSATION_DRAFT_PUBLISH,
        )
        log_handled_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to publish conversation draft changed event (non-critical).",
            operation=OPERATION_CONVERSATION_DRAFT_PUBLISH,
            level="debug",
            details={
                "user_id": int(user_id),
                "conv_id": conv_id,
                "client_id": client_id,
                "deleted": deleted,
            },
        )
