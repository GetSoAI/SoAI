"""SoAI - Manual compaction start-state preparation [backend/features/api/routes/webui/conversation_agent_compaction/start_state_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from starlette.requests import Request

from core.agent.todo_state_models import AgentTurnTodoState
from core.errors.exceptions import ConfigurationError, StateError, ValidationError
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.agent.runtime.turn_todo_state import load_turn_todo_state
from features.api.routes.webui.conversation_agent_compaction.context import (
    resolve_compaction_model_and_budget,
    resolve_model_id,
)
from features.api.routes.webui.conversation_agent_compaction.running_turns import (
    require_no_running_agent_turns,
)
from features.api.routes.webui.conversation_agent_compaction.start_state_claims import (
    build_manual_compaction_turn_identity,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.current_user import CurrentUser
from features.api.runtime.errors import raise_invalid_request, raise_server_error

__all__ = (
    "ManualCompactionConversationContext",
    "ManualCompactionPreparedState",
    "load_manual_compaction_conversation_context",
    "prepare_manual_compaction_start_claim",
)


@dataclass(frozen=True, slots=True)
class ManualCompactionConversationContext:
    started_at_ms: int
    conversation_record: JSONDict
    resolved_conv_id: str


@dataclass(frozen=True, slots=True)
class ManualCompactionPreparedState:
    started_at_ms: int
    conversation_record: JSONDict
    resolved_conv_id: str
    model: str
    context_window_tokens: int
    mode: str
    compaction_limit: int
    todo_state: AgentTurnTodoState
    turn_id: str
    turn_cancellation_id: str


async def load_manual_compaction_conversation_context(
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    *,
    conv_id: str,
) -> ManualCompactionConversationContext:
    started_at_ms = int(epoch_ms())
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    return ManualCompactionConversationContext(
        started_at_ms=started_at_ms,
        conversation_record=conversation_context.record,
        resolved_conv_id=conversation_context.resolved_conv_id,
    )


async def prepare_manual_compaction_start_claim(
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    *,
    conversation_context: ManualCompactionConversationContext,
    model_candidate: str | None,
) -> ManualCompactionPreparedState:
    try:
        resolved_model_candidate = model_candidate
        if resolved_model_candidate is None:
            resolved_model_candidate = resolve_model_id(conversation_context.conversation_record)
        await require_no_running_agent_turns(
            request,
            api_context=api_context,
            conv_id=conversation_context.resolved_conv_id,
            user_id=current_user["id"],
        )
        model, context_window_tokens, mode, compaction_limit = (
            await resolve_compaction_model_and_budget(
                api_context=api_context,
                conversation_record=conversation_context.conversation_record,
                model_candidate=resolved_model_candidate,
            )
        )
        todo_state = await load_turn_todo_state(
            database_agent_todo_state=api_context.dependencies.database_agent_todo_state,
            conv_id=conversation_context.resolved_conv_id,
            user_id=current_user["id"],
        )
        turn_id, turn_cancellation_id = build_manual_compaction_turn_identity()
    except (StateError, ValidationError) as exception:
        raise_invalid_request(request, str(exception))
    except ConfigurationError as exception:
        raise_server_error(request, str(exception))
    return ManualCompactionPreparedState(
        started_at_ms=conversation_context.started_at_ms,
        conversation_record=conversation_context.conversation_record,
        resolved_conv_id=conversation_context.resolved_conv_id,
        model=model,
        context_window_tokens=context_window_tokens,
        mode=mode,
        compaction_limit=compaction_limit,
        todo_state=todo_state,
        turn_id=turn_id,
        turn_cancellation_id=turn_cancellation_id,
    )
