"""SoAI - WebSocket agent turn admission without initial inference [backend/features/api/routes/system/events/websocket_chat_stream/agent_turn_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from features.agent.runtime.execution_preparation import (
    build_agent_turn_engine_dependencies,
)
from features.agent.runtime.turn_lifecycle.claim import (
    claim_agent_turn_for_streaming_execution,
)
from features.agent.runtime.turn_todo_state import parse_agent_todo_state_payload
from features.api.routes.system.events.websocket_chat_stream.admission_cleanup import (
    run_ws_chat_stream_admission_lifecycle,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.orchestrator.types import MCPToolContext
    from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
    from core.runtime.request_context import RequestContext
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
    from features.api.runtime.context import ApiContext
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("start_ws_chat_stream_agent_turn_admission",)

OPERATION_WS_AGENT_TURN_ADMISSION_RELEASE_QUOTA = (
    "webui_ws_chat_stream.agent_turn_admission.release_quota"
)
_QUOTA_RELEASE_MESSAGE = "Failed to release chat stream quota after agent turn admission failure."


async def start_ws_chat_stream_agent_turn_admission(
    *,
    session: AssistantTimelineSession,
    api_context: ApiContext,
    request_context: RequestContext,
    runtime: AssistantTimelineRuntime,
    tool_context: MCPToolContext | None,
    prepared_agent_request: PreparedExecutionRequest | None,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
    logger: TraceLogger,
) -> str:
    webui_manager = api_context.dependencies.webui_manager

    async def admit_agent_turn() -> str:
        session.start()
        if tool_context is None:
            raise ValidationError("WebSocket agent turn admission requires tool context.")
        if prepared_agent_request is None:
            raise ValidationError("Prepared agent request state is unavailable.")
        async with runtime.quota_release_lock:
            turn_primitives, _turn_record, first_iteration_cancellation_id = (
                await claim_agent_turn_for_streaming_execution(
                    deps=build_agent_turn_engine_dependencies(
                        api_dependencies=api_context.dependencies,
                        logger=logger,
                    ),
                    context=request_context,
                    tool_context=tool_context,
                    settings=prepared_agent_request.agent_settings,
                    requested_model=prepared_agent_request.requested_model,
                    todo_state=parse_agent_todo_state_payload(
                        prepared_agent_request.todo_state,
                    ),
                )
            )
            runtime.agent_turn_id = request_context.agent_turn_id
            runtime.agent_turn_execution_token = request_context.agent_turn_execution_token
            runtime.agent_turn_cancellation_id = turn_primitives.turn_cancellation_id
        return first_iteration_cancellation_id

    return await run_ws_chat_stream_admission_lifecycle(
        admission=admit_agent_turn,
        api_context=api_context,
        request_context=request_context,
        runtime=runtime,
        knowledge_prompt_claim=knowledge_prompt_claim,
        logger=logger,
        database_api_keys=webui_manager.database_api_keys,
        quota_operation=OPERATION_WS_AGENT_TURN_ADMISSION_RELEASE_QUOTA,
        quota_message=_QUOTA_RELEASE_MESSAGE,
        release_on_unexpected=False,
    )
