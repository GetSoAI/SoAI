"""SoAI - Prepared manual compaction start-state finalization [backend/features/api/routes/webui/conversation_agent_compaction/prepared_start_state_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from starlette.requests import Request

from features.api.routes.webui.conversation_agent_compaction.start_state_claims import (
    ManualCompactionStartState,
    finalize_manual_compaction_start_state,
    resolve_manual_compaction_start_message_index,
)
from features.api.routes.webui.conversation_agent_compaction.start_state_preparation import (
    ManualCompactionPreparedState,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.current_user import CurrentUser

__all__ = ("finalize_prepared_manual_compaction_start_state",)


async def finalize_prepared_manual_compaction_start_state(
    *,
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    prepared_state: ManualCompactionPreparedState,
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
    manual_regeneration_request_json: str | None = None,
    manual_regeneration_expected_revision: int | None = None,
) -> ManualCompactionStartState:
    message_index = await resolve_manual_compaction_start_message_index(
        api_context=api_context,
        user_id=current_user["id"],
        conv_id=prepared_state.resolved_conv_id,
        replace_assistant_at_ms=replace_assistant_at_ms,
    )
    return await finalize_manual_compaction_start_state(
        request=request,
        user_id=current_user["id"],
        conv_id=prepared_state.resolved_conv_id,
        model=prepared_state.model,
        mode=prepared_state.mode,
        compaction_limit=prepared_state.compaction_limit,
        context_window_tokens=prepared_state.context_window_tokens,
        turn_id=prepared_state.turn_id,
        turn_cancellation_id=prepared_state.turn_cancellation_id,
        started_at_ms=prepared_state.started_at_ms,
        message_index=message_index,
        todo_state=prepared_state.todo_state,
        replace_assistant_at_ms=replace_assistant_at_ms,
        replace_tool_call_id=replace_tool_call_id,
        manual_regeneration_request_json=manual_regeneration_request_json,
        manual_regeneration_expected_revision=manual_regeneration_expected_revision,
    )
