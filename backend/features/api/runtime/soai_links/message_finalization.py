"""SoAI - SoAI path link message finalization [backend/features/api/runtime/soai_links/message_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.workspaces.soai_path_link_codec import (
    extract_soai_path_tokens,
    strip_soai_path_tokens,
)
from features.api.runtime.conversation_workspace_scope import (
    build_conversation_workspace_scope,
)
from features.api.runtime.soai_links.content_parts import (
    base_parts_with_single_text,
    content_has_soai_path_tokens,
    message_content_parts,
    message_copy,
    raw_text_part,
)
from features.api.runtime.soai_links.resolution import resolve_soai_path_token

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.runtime.conversation_workspace_scope import (
        ConversationWorkspaceScope,
    )
    from features.api.runtime.user_types import CurrentUser

__all__ = ("finalize_soai_links_in_messages",)


async def _finalize_user_message(
    *,
    message: JSONDict,
    scope: ConversationWorkspaceScope,
) -> JSONDict:
    content = message.get("content")
    parts = message_content_parts(content)
    raw_text = raw_text_part(parts)
    if raw_text is None:
        return message
    tokens = extract_soai_path_tokens(raw_text)
    if not tokens:
        return message
    base_parts = base_parts_with_single_text(parts, strip_soai_path_tokens(raw_text))
    resolved_parts: list[JSONDict] = []
    for token in tokens:
        resolved_parts.append(resolve_soai_path_token(scope=scope, token=token))
    message["content"] = [*base_parts, *resolved_parts]
    return message


async def finalize_soai_links_in_messages(
    *,
    messages: list[JSONDict],
    current_user: CurrentUser,
    conversation_record: JSONDict,
    api_context: ApiContext,
) -> list[JSONDict]:
    finalized: list[JSONDict] = []
    scope: ConversationWorkspaceScope | None = None
    for message in messages:
        next_message = message_copy(message)
        if next_message.get("role") != "user":
            finalized.append(next_message)
            continue
        requires_scope = content_has_soai_path_tokens(next_message.get("content"))
        if requires_scope and scope is None:
            scope = build_conversation_workspace_scope(
                current_user=current_user,
                conversation_record=conversation_record,
                api_context=api_context,
            )
        if scope is None:
            finalized.append(next_message)
            continue
        finalized.append(await _finalize_user_message(message=next_message, scope=scope))
    return finalized
