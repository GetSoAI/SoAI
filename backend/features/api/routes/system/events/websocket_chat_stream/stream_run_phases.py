"""SoAI - WebSocket chat stream pre-stream lifecycle phases and non-agent run arm [backend/features/api/routes/system/events/websocket_chat_stream/stream_run_phases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.websocket_chat_stream.admitted_abort_cancellation import (
    cancel_admitted_ws_chat_stream_task_for_abort,
)
from features.api.routes.system.events.websocket_chat_stream.completion_followups import (
    handle_non_agent_stream_completion_followups,
)
from features.api.routes.system.events.websocket_chat_stream.finalization import (
    finalize_ws_chat_stream_cancellation_noncritical,
)
from features.api.runtime.chat_execution.runtime_quota import (
    release_ws_chat_stream_runtime_quota_noncritical,
)
from features.api.runtime.knowledge_prompt_delivery import (
    release_knowledge_prompt_claim_noncritical,
)
from features.api.streaming.assistant_timeline.non_agent.stream_execution import (
    execute_timeline_non_agent_stream,
)
from features.assistant_timeline.assistant_timeline_session import AssistantTimelineSession

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.rag.knowledge_prompt_types import KnowledgePromptDeliveryClaim
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import TaskRegistryProtocol
    from features.agent.runtime.streaming_inference_admission import (
        AgentStreamingTaskBundle,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
__all__ = (
    "abort_admitted_ws_chat_stream_if_cancelled",
    "abort_ws_chat_stream_before_admission_if_cancelled",
    "run_ws_chat_stream_non_agent_arm",
)

OPERATION_PRE_ADMISSION_ABORT_RELEASE_QUOTA = (
    "webui_ws_chat_stream.run.release_quota_before_admission_abort"
)
_PRE_ADMISSION_QUOTA_RELEASE_MESSAGE = (
    "Failed to release chat stream quota during pre-admission cancellation abort."
)
_DEFAULT_ABORT_REASON = "Chat stream was cancelled."


def _resolve_abort_reason(cancellation_reason: str | None) -> str:
    if cancellation_reason is not None and cancellation_reason.strip():
        return cancellation_reason.strip()
    return _DEFAULT_ABORT_REASON


async def abort_ws_chat_stream_before_admission_if_cancelled(
    *,
    api_context: ApiContext,
    session: AssistantTimelineSession,
    context: RequestContext,
    tool_context: MCPToolContext | None,
    knowledge_prompt_claim: KnowledgePromptDeliveryClaim | None,
    logger: LoggerProtocol,
) -> bool:
    runtime = session.runtime
    if not runtime.cancellation_requested:
        return False
    await release_knowledge_prompt_claim_noncritical(
        api_dependencies=api_context.dependencies,
        claim=knowledge_prompt_claim,
        logger=logger,
        trace_id=context.trace_id,
    )
    await release_ws_chat_stream_runtime_quota_noncritical(
        database_api_keys=api_context.dependencies.webui_manager.database_api_keys,
        runtime=runtime,
        logger=logger,
        trace_id=context.trace_id,
        operation=OPERATION_PRE_ADMISSION_ABORT_RELEASE_QUOTA,
        message=_PRE_ADMISSION_QUOTA_RELEASE_MESSAGE,
    )
    await finalize_ws_chat_stream_cancellation_noncritical(
        session=session,
        database_agent_turns=api_context.dependencies.database_agent_turns,
        task_registry=api_context.dependencies.task_registry,
        logger=logger,
        context=context,
        tool_context=tool_context,
    )
    return True


async def abort_admitted_ws_chat_stream_if_cancelled(
    *,
    api_context: ApiContext,
    session: AssistantTimelineSession,
    context: RequestContext,
    tool_context: MCPToolContext | None,
    bundle: AgentStreamingTaskBundle,
    logger: LoggerProtocol,
) -> bool:
    runtime = session.runtime
    if not runtime.cancellation_requested:
        return False
    await cancel_admitted_ws_chat_stream_task_for_abort(
        api_context=api_context,
        context=context,
        bundle=bundle,
        reason=_resolve_abort_reason(runtime.cancellation_reason),
        logger=logger,
    )
    await finalize_ws_chat_stream_cancellation_noncritical(
        session=session,
        database_agent_turns=api_context.dependencies.database_agent_turns,
        task_registry=api_context.dependencies.task_registry,
        logger=logger,
        context=context,
        tool_context=tool_context,
    )
    return True


async def run_ws_chat_stream_non_agent_arm(
    *,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    session: AssistantTimelineSession,
    context: RequestContext,
    bundle: AgentStreamingTaskBundle,
    registry: TaskRegistryProtocol,
) -> None:
    runtime = session.runtime
    final_non_agent_task_id = await execute_timeline_non_agent_stream(
        api_context.dependencies,
        stream_dependencies=stream_dependencies,
        session=session,
        context=context,
        bundle=bundle,
        model=runtime.model_id,
        include_usage=True,
        emit_done_marker=True,
        allow_image_events=False,
        task_lookup=lambda task_id: registry.get(task_id, force_refresh=True),
    )
    if final_non_agent_task_id is not None and final_non_agent_task_id:
        await handle_non_agent_stream_completion_followups(
            api_dependencies=api_context.dependencies,
            runtime=runtime,
            task_id=final_non_agent_task_id,
        )
