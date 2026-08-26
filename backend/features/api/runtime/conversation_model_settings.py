"""SoAI - Conversation model_settings persistence helpers [backend/features/api/runtime/conversation_model_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.conversations.settings_authority import (
    resolve_conversation_settings_authority,
)
from core.errors.exceptions import StateError
from core.model_settings.normalization import normalize_model_selection_settings
from core.validation.epoch import is_unix_epoch_ms
from features.api.runtime.conversation_settings_mutation import (
    require_conversation_settings_mutable,
)
from features.api.runtime.errors import raise_not_found
from features.api.runtime.model_settings_mcp import (
    normalize_model_settings_mcp_for_owner,
)
from features.api.runtime.webui_records import webui_fetch_or_404

if TYPE_CHECKING:
    from fastapi import Request

    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("update_conversation_model_settings",)


async def update_conversation_model_settings(
    request: Request,
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    model_settings: JSONDict,
) -> JSONDict:
    existing_record = await webui_fetch_or_404(
        request,
        api_context.dependencies.database_conversations.get_conversation(conv_id, user_id),
        message="Conversation not found.",
    )
    authority = resolve_conversation_settings_authority(existing_record)
    require_conversation_settings_mutable(request, authority)
    normalized_settings = normalize_model_settings_mcp_for_owner(
        request,
        normalize_model_selection_settings(model_settings),
        is_automation=False,
        disallowed_unqualified_tools=load_automation_disallowed_unqualified_tools(
            api_context.dependencies.config,
        ),
    )
    commit = await api_context.dependencies.database_conversations.update_conversation_settings(
        conv_id,
        user_id,
        normalized_settings,
    )
    if commit is None:
        raise_not_found(request, "Conversation not found.")
    updated_record = commit.conversation
    last_modified_at_ms = updated_record.get("last_modified_at_ms")
    if not is_unix_epoch_ms(last_modified_at_ms, enforce_maximum=False):
        raise StateError("Conversation update returned invalid last_modified_at_ms.")
    normalized_record: JSONDict = dict(updated_record)
    normalized_record["model_settings"] = normalized_settings
    return normalized_record
