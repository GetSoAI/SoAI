"""SoAI - Manual compaction regeneration start-state entrypoint [backend/features/api/routes/webui/conversation_agent_compaction/regenerate_start_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from starlette.requests import Request

from core.errors.exceptions import ValidationError
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
from features.api.runtime.errors import raise_invalid_request
from features.api.schemas.conversations import AgentCompactionRegenerateRequest

__all__ = ("resolve_manual_compaction_regenerate_start_state",)


async def resolve_manual_compaction_regenerate_start_state(
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    conv_id: str,
    payload: AgentCompactionRegenerateRequest,
) -> ManualCompactionStartState:
    conversation_context = await load_manual_compaction_conversation_context(
        request,
        api_context=api_context,
        current_user=current_user,
        conv_id=conv_id,
    )
    try:
        replace_tool_call_id = (
            await api_context.dependencies.database_messages.get_context_compaction_tool_call_id(
                conversation_context.resolved_conv_id,
                current_user["id"],
                assistant_turn_at_ms=payload.assistant_turn_at_ms,
            )
        )
        if replace_tool_call_id is None:
            raise ValidationError("Conversation messages could not be loaded.")
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    prepared_state = await prepare_manual_compaction_start_claim(
        request,
        api_context,
        current_user,
        conversation_context=conversation_context,
        model_candidate=None,
    )
    return await finalize_prepared_manual_compaction_start_state(
        request=request,
        api_context=api_context,
        current_user=current_user,
        prepared_state=prepared_state,
        bind_owner="webui.agent.compact.regenerate.claim",
        operation="webui.agent.compact.regenerate.resolve_start_state",
        replace_assistant_at_ms=payload.assistant_turn_at_ms,
        replace_tool_call_id=replace_tool_call_id,
    )
