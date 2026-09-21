"""SoAI - Effective conversation execution settings [backend/features/api/runtime/conversation_execution_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.conversation_model_settings_resolution import (
    resolve_conversation_model_settings,
)
from core.conversations.settings_authority import (
    resolve_conversation_settings_authority,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("resolve_conversation_execution_settings",)


async def resolve_conversation_execution_settings(
    api_context: ApiContext,
    *,
    user_id: int,
    conversation_record: JSONDict,
) -> JSONDict:
    authority = resolve_conversation_settings_authority(conversation_record)
    return await resolve_conversation_model_settings(
        user_id=user_id,
        model_settings_snapshot=authority.model_settings,
        database_chat_identity_defaults=(api_context.dependencies.database_chat_identity_defaults),
        database_chat_model_defaults=api_context.dependencies.database_chat_model_defaults,
    )
