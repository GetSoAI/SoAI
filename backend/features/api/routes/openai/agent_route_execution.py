"""SoAI - Shared agent route execution preparation [backend/features/api/routes/openai/agent_route_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.protocols import LoggerProtocol
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.tasks.type_catalog import TaskTypeId
from core.types.json_value import copy_json_dict
from core.users.user_id import coerce_optional_user_id, require_user_id
from features.agent.runtime.context_compaction.outcome import (
    COMPACTION_SUMMARY_SOURCE_DETERMINISTIC,
)
from features.agent.runtime.execution_preparation import AgentRuntimePreparation
from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
from features.api.routes.openai.internal_protocols import AgentRuntimePreparerProtocol
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_invalid_request
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.activity_result import (
        PreparedAutoCompactionSnapshot,
    )

__all__ = (
    "PreparedAgentRouteExecution",
    "create_agent_iteration_context",
    "prepare_agent_route_execution",
)


@dataclass(frozen=True, slots=True)
class PreparedAgentRouteExecution:
    initial_messages: list[JSONDict]
    initial_boundary_source_messages: list[JSONDict]
    runtime_preparation: AgentRuntimePreparation
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None
    prepared_auto_compaction: PreparedAutoCompactionSnapshot | None
    base_request_payload: JSONDict


def _should_recompact_preflight_snapshot(
    *,
    snapshot: PreparedAutoCompactionSnapshot | None,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
) -> bool:
    if snapshot is None or summarize_messages is None:
        return False
    return snapshot.metadata.summary_source == COMPACTION_SUMMARY_SOURCE_DETERMINISTIC


def _resolve_conversation_user_id(
    *,
    api_context: ApiContext,
    context: RequestContext,
    tool_context: MCPToolContext,
) -> int:
    conversation_user_id = require_user_id(tool_context.user_id)
    request_user_id = coerce_optional_user_id(context.user_id)
    if (
        request_user_id is not None
        and request_user_id > 0
        and request_user_id != conversation_user_id
    ):
        raise_invalid_request(
            api_context.request,
            "Authenticated user mismatch for conversation-scoped agent request.",
        )
    return conversation_user_id


def create_agent_iteration_context(
    context: RequestContext,
    cancellation_id: str,
    agent_iteration_index: int,
    task_id: str | None = None,
) -> RequestContext:
    if not context.trace_id.strip():
        raise ValidationError("Agent iteration context requires a non-empty trace_id.")
    return clone_request_context(
        context,
        task_id=task_id,
        cancellation_id=cancellation_id,
        agent_iteration_index=agent_iteration_index,
    )


async def prepare_agent_route_execution(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    prepared_agent_request: PreparedExecutionRequest,
    task_type: TaskTypeId,
    logger: LoggerProtocol,
    prepare_runtime: AgentRuntimePreparerProtocol,
    prepare_summarizer: Callable[..., Callable[[list[JSONDict]], Awaitable[str]] | None],
) -> PreparedAgentRouteExecution:
    prepared_state = prepared_agent_request
    conversation_user_id = _resolve_conversation_user_id(
        api_context=api_context,
        context=context,
        tool_context=tool_context,
    )
    if (
        prepared_state.conv_id != tool_context.conv_id
        or prepared_state.user_id != conversation_user_id
    ):
        raise_invalid_request(
            api_context.request,
            "Prepared agent request state does not match the conversation request.",
        )
    context.user_id = conversation_user_id
    base_request_payload = copy_json_dict(prepared_state.final_payload)
    runtime_preparation = await prepare_runtime(
        request=request,
        api_dependencies=api_context.dependencies,
        context=context,
        tool_context=tool_context,
        prepared_agent_request=prepared_state,
        logger=logger,
    )
    settings = runtime_preparation.settings
    summarize_messages = prepare_summarizer(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        context=context,
        request_json=base_request_payload,
        mode=settings.mode,
        compaction_context_window_tokens=settings.compaction_context_window_tokens,
        task_type=task_type,
        owner_type=runtime_preparation.owner_type,
        owner_id=runtime_preparation.owner_id,
    )
    prepared_auto_compaction = prepared_state.prepared_auto_compaction
    initial_messages = [
        dict(message) for message in prepared_state.prepared_messages_after_compaction
    ]
    if _should_recompact_preflight_snapshot(
        snapshot=prepared_auto_compaction,
        summarize_messages=summarize_messages,
    ):
        prepared_auto_compaction = None
        initial_messages = [
            dict(message) for message in prepared_state.prepared_messages_before_compaction
        ]
    return PreparedAgentRouteExecution(
        initial_messages=initial_messages,
        initial_boundary_source_messages=prepared_state.boundary_source_messages,
        base_request_payload=base_request_payload,
        runtime_preparation=runtime_preparation,
        summarize_messages=summarize_messages,
        prepared_auto_compaction=prepared_auto_compaction,
    )
