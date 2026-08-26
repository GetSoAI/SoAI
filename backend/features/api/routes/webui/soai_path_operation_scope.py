"""SoAI - SoAI path operation conversation scope [backend/features/api/routes/webui/soai_path_operation_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from features.api.runtime.context import ApiContext
from features.api.runtime.conversation_access import require_conversation_access
from features.api.runtime.conversation_workspace_scope import (
    ConversationWorkspaceScope,
    build_conversation_workspace_scope,
)
from features.api.runtime.current_user import CurrentUser

__all__ = ("conversation_soai_path_scope",)


async def conversation_soai_path_scope(
    *,
    request: Request,
    conv_id: str,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> ConversationWorkspaceScope:
    conversation_record = await require_conversation_access(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    return build_conversation_workspace_scope(
        current_user=current_user,
        conversation_record=conversation_record,
        api_context=api_context,
    )
