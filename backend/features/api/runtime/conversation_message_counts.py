"""SoAI - Conversation message count resolution [backend/features/api/runtime/conversation_message_counts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.runtime.protocols import RequestProtocol
from core.validation.integers import is_non_negative_strict_int
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import (
    raise_not_found,
    raise_service_unavailable,
)

__all__ = ("resolve_conversation_message_count",)


async def resolve_conversation_message_count(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
) -> int:
    try:
        database_messages = api_context.dependencies.database_messages
    except AttributeError:
        database_messages = None
    if database_messages is None:
        try:
            webui_manager = api_context.dependencies.webui_manager
        except AttributeError:
            webui_manager = None
        if webui_manager is None:
            database_messages = None
        else:
            try:
                database_messages = webui_manager.database_messages
            except AttributeError:
                database_messages = None
    if database_messages is None:
        raise_service_unavailable(request, "Conversation message state is unavailable.")
    message_count = await database_messages.count_messages(conv_id, user_id)
    if message_count is None:
        raise_not_found(request, "Conversation not found.")
    if not is_non_negative_strict_int(message_count):
        raise_service_unavailable(request, "Conversation message state is unavailable.")
    return message_count
