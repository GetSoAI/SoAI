"""SoAI - WebSocket chat stream admission and claim handling [backend/features/api/routes/system/events/websocket_chat_stream/stream_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.chat_stream.initial_task_bundle import (
    create_ws_chat_stream_initial_task_bundle,
)
from features.api.routes.system.events.websocket_chat_stream.admission_cleanup import (
    run_ws_chat_stream_admission_lifecycle,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.orchestrator.types import MCPToolContext
    from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
    from features.agent.runtime.streaming_inference_admission import (
        AgentStreamingTaskBundle,
    )
    from features.api.runtime.context import ApiContext
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("start_ws_chat_stream_admission",)

OPERATION_WS_CHAT_STREAM_CREATE_TASK_RELEASE_QUOTA = (
    "webui_ws_chat_stream.create_task.release_quota"
)
_QUOTA_RELEASE_MESSAGE = "Failed to release chat stream quota after admission failure."


async def start_ws_chat_stream_admission(
    *,
    session: AssistantTimelineSession,
    api_context: ApiContext,
    request_context: RequestContext,
    runtime: AssistantTimelineRuntime,
    request_json: JSONDict,
    tool_context: MCPToolContext | None,
    prepared_agent_request: PreparedExecutionRequest | None,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
    logger: TraceLogger,
) -> AgentStreamingTaskBundle:
    webui_manager = api_context.dependencies.webui_manager

    async def admit_stream() -> AgentStreamingTaskBundle:
        session.start()
        return await create_ws_chat_stream_initial_task_bundle(
            api_context.dependencies,
            logger=logger,
            context=request_context,
            runtime=runtime,
            request_json=request_json,
            tool_context=tool_context,
            prepared_agent_request=prepared_agent_request,
        )

    return await run_ws_chat_stream_admission_lifecycle(
        admission=admit_stream,
        api_context=api_context,
        request_context=request_context,
        runtime=runtime,
        knowledge_prompt_claim=knowledge_prompt_claim,
        logger=logger,
        database_api_keys=webui_manager.database_api_keys,
        quota_operation=OPERATION_WS_CHAT_STREAM_CREATE_TASK_RELEASE_QUOTA,
        quota_message=_QUOTA_RELEASE_MESSAGE,
        release_on_unexpected=True,
    )
