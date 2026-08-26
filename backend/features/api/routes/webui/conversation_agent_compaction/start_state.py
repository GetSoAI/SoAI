"""SoAI - Manual compaction start-state entrypoint [backend/features/api/routes/webui/conversation_agent_compaction/start_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from starlette.requests import Request

from features.api.routes.webui.conversation_agent_compaction.prepared_start_state_finalization import (
    finalize_prepared_manual_compaction_start_state,
)
from features.api.routes.webui.conversation_agent_compaction.start_state_claims import (
    ManualCompactionStartState,
)
from features.api.routes.webui.conversation_agent_compaction.start_state_preparation import (
    load_manual_compaction_conversation_context,
    prepare_manual_compaction_start_claim,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.current_user import CurrentUser
from features.api.schemas.conversations import AgentCompactionStartRequest

__all__ = ("resolve_manual_compaction_start_state",)


async def resolve_manual_compaction_start_state(
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    conv_id: str,
    payload: AgentCompactionStartRequest,
) -> ManualCompactionStartState:
    conversation_context = await load_manual_compaction_conversation_context(
        request,
        api_context,
        current_user,
        conv_id=conv_id,
    )
    prepared_state = await prepare_manual_compaction_start_claim(
        request,
        api_context,
        current_user,
        conversation_context=conversation_context,
        model_candidate=payload.model,
    )
    return await finalize_prepared_manual_compaction_start_state(
        request=request,
        api_context=api_context,
        current_user=current_user,
        prepared_state=prepared_state,
        bind_owner="webui.agent_compaction.claim",
        operation="webui.agent_compaction.resolve_start_state",
        replace_assistant_at_ms=None,
        replace_tool_call_id=None,
    )
