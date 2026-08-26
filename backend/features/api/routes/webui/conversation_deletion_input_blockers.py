"""SoAI - Durable conversation input blockers before deletion [backend/features/api/routes/webui/conversation_deletion_input_blockers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.runtime.errors import raise_conflict

if TYPE_CHECKING:
    from fastapi import Request

    from core.conversations.conversation_input_active_state import ActiveConversationInputSummary
    from core.types.json import JSONValue
    from features.api.runtime.context import ApiContext

__all__ = ("require_no_active_conversation_inputs",)

CONVERSATION_DELETE_CONFLICT_CODE = "conversation_delete_conflict"
ACTIVE_CONVERSATION_INPUTS_REASON = "active_conversation_inputs"


def _build_blocker_detail(
    conv_id: str,
    summary: ActiveConversationInputSummary,
) -> dict[str, JSONValue]:
    return {
        "conv_id": conv_id,
        "active_input_count": summary.active_count,
        "active_states": list(summary.active_states),
    }


async def require_no_active_conversation_inputs(
    *,
    request: Request,
    api_context: ApiContext,
    user_id: int,
    conv_ids: tuple[str, ...],
) -> None:
    requested_conv_ids = tuple(
        dict.fromkeys(conv_id.strip() for conv_id in conv_ids if conv_id.strip()),
    )
    if not requested_conv_ids:
        return
    database_conversations = api_context.dependencies.database_conversations
    summaries = await database_conversations.summarize_active_conversation_inputs_for_deletion(
        user_id,
    )
    blockers: list[JSONValue] = []
    for conv_id in requested_conv_ids:
        summary = summaries.get(conv_id)
        if summary is not None and summary.has_active_inputs:
            blockers.append(_build_blocker_detail(conv_id, summary))
    if not blockers:
        return
    raise_conflict(
        request,
        "Conversation deletion requires durable conversation inputs to settle.",
        error_type=CONVERSATION_DELETE_CONFLICT_CODE,
        extra={"reason": ACTIVE_CONVERSATION_INPUTS_REASON, "conversations": blockers},
    )
