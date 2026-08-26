"""SoAI - Conversation access helper for API runtime [backend/features/api/runtime/conversation_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request

from features.api.runtime.webui_records import webui_fetch_or_404

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "ConversationAccessContext",
    "require_conversation_access",
    "require_conversation_access_context",
    "resolve_conversation_access_id",
)

DEFAULT_CONVERSATION_ACCESS_NOT_FOUND_MESSAGE = (
    "Conversation not found or you do not have permission to access it."
)


@dataclass(frozen=True, slots=True)
class ConversationAccessContext:
    record: JSONDict
    resolved_conv_id: str


def resolve_conversation_access_id(record: JSONDict, fallback_conv_id: str) -> str:
    return str(record.get("id") or fallback_conv_id)


async def require_conversation_access(
    request: Request,
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    message: str = DEFAULT_CONVERSATION_ACCESS_NOT_FOUND_MESSAGE,
) -> JSONDict:
    return await webui_fetch_or_404(
        request,
        api_context.dependencies.database_conversations.get_conversation(conv_id, user_id),
        message=message,
    )


async def require_conversation_access_context(
    request: Request,
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    message: str = DEFAULT_CONVERSATION_ACCESS_NOT_FOUND_MESSAGE,
) -> ConversationAccessContext:
    record = await require_conversation_access(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
        message=message,
    )
    return ConversationAccessContext(
        record=record,
        resolved_conv_id=resolve_conversation_access_id(record, conv_id),
    )
