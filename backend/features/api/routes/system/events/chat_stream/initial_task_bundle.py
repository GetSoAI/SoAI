"""SoAI - WebSocket chat stream initial task bundle creation [backend/features/api/routes/system/events/chat_stream/initial_task_bundle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.orchestrator.tool_context_identity_validation import (
    build_tool_context_message_index_mismatch_message,
)
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from features.agent.runtime.execution_preparation import (
    build_agent_turn_engine_dependencies,
)
from features.agent.runtime.streaming_inference_admission import (
    create_streaming_inference_task,
)
from features.agent.runtime.turn_lifecycle.claim import (
    claim_agent_turn_for_streaming_execution,
)
from features.agent.runtime.turn_todo_state import parse_agent_todo_state_payload
from features.api.runtime.chat_execution.task_metadata import (
    build_ws_chat_stream_task_metadata,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict
    from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
    from features.agent.runtime.streaming_inference_admission import (
        AgentStreamingTaskBundle,
    )
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("create_ws_chat_stream_initial_task_bundle",)


def _with_ws_usage_reporting(request_json: JSONDict) -> JSONDict:
    payload: JSONDict = dict(request_json)
    stream_options = payload.get("stream_options")
    if isinstance(stream_options, dict):
        payload["stream_options"] = {**stream_options, "include_usage": True}
        return payload
    payload["stream_options"] = {"include_usage": True}
    return payload


async def create_ws_chat_stream_initial_task_bundle(
    api_dependencies: ApiDependencies,
    *,
    logger: TraceLogger,
    context: RequestContext,
    runtime: AssistantTimelineRuntime,
    request_json: JSONDict,
    tool_context: MCPToolContext | None,
    prepared_agent_request: PreparedExecutionRequest | None,
) -> AgentStreamingTaskBundle:
    context_tool_context = context.mcp_tool_context
    if context_tool_context is not None and not isinstance(context_tool_context, MCPToolContext):
        raise ValidationError("WebSocket chat stream RequestContext.mcp_tool_context is invalid.")
    if tool_context is None:
        if isinstance(context_tool_context, MCPToolContext):
            raise ValidationError("WebSocket chat stream tool context mismatch.")
    else:
        if not isinstance(context_tool_context, MCPToolContext):
            raise ValidationError("WebSocket chat stream tool context mismatch.")
        if int(tool_context.message_index) != int(runtime.message_index):
            raise ValidationError(
                build_tool_context_message_index_mismatch_message(
                    surface="WebSocket chat stream",
                    conv_id=runtime.conv_id,
                    assistant_at_ms=runtime.assistant_at_ms,
                    tool_context_message_index=tool_context.message_index,
                    runtime_message_index=runtime.message_index,
                ),
            )
    async with runtime.quota_release_lock:
        if tool_context is not None:
            if prepared_agent_request is None:
                raise ValidationError("Prepared agent request state is unavailable.")
            (
                turn_primitives,
                _turn_record,
                first_iteration_cancellation_id,
            ) = await claim_agent_turn_for_streaming_execution(
                deps=build_agent_turn_engine_dependencies(
                    api_dependencies=api_dependencies,
                    logger=logger,
                ),
                context=context,
                tool_context=tool_context,
                settings=prepared_agent_request.agent_settings,
                requested_model=prepared_agent_request.requested_model,
                todo_state=parse_agent_todo_state_payload(prepared_agent_request.todo_state),
            )
            runtime.agent_turn_id = context.agent_turn_id
            runtime.agent_turn_execution_token = context.agent_turn_execution_token
            runtime.agent_turn_cancellation_id = turn_primitives.turn_cancellation_id
            admission_request_json = _with_ws_usage_reporting(
                dict(prepared_agent_request.final_payload),
            )
            admission_cancellation_id = first_iteration_cancellation_id
        else:
            admission_request_json = _with_ws_usage_reporting(dict(request_json))
            admission_cancellation_id = runtime.task_cancellation_id
        bundle = await create_streaming_inference_task(
            api_dependencies,
            context=context,
            request_json=admission_request_json,
            task_type=TASK_TYPE_CHAT_COMPLETION,
            user_id=runtime.user_id,
            owner_type="conversation",
            owner_id=runtime.conv_id,
            cancellation_id=admission_cancellation_id,
            metadata=build_ws_chat_stream_task_metadata(runtime=runtime),
            request_source=REQUEST_SOURCE_WEBUI_WS,
        )
        runtime.active_task_id = bundle.task.task_id
        runtime.clear_quota_reservation()
    return bundle
