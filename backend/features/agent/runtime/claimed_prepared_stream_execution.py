"""SoAI - Claimed prepared stream execution helper [backend/features/agent/runtime/claimed_prepared_stream_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.agent.settings_types import AgentSettings
from core.errors.exceptions import ValidationError
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.types.json import JSONDict
from features.agent.runtime.claimed_stream_execution import execute_claimed_stream
from features.agent.runtime.prepared_stream_execution import (
    AgentStreamingTaskBundle,
    PreparedStreamingTurnExecution,
    execute_prepared_streaming_turn,
)
from features.agent.runtime.turn_engine import AgentTurnEngineDependencies
from features.agent.runtime.turn_iteration_policy_types import AgentOutputPublicationMode

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from features.agent.runtime.context_compaction.activity_result import (
        PreparedAutoCompactionSnapshot,
    )
    from features.api.runtime.container.types import ApiDependencies
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = ("execute_claimed_prepared_stream",)


async def execute_claimed_prepared_stream(
    api_dependencies: ApiDependencies,
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    requested_model: str | None,
    settings: AgentSettings,
    todo_state: JSONDict | None,
    initial_messages: list[JSONDict],
    initial_boundary_source_messages: list[JSONDict],
    base_request_payload: JSONDict,
    owner_id: str,
    cancellation_id: str,
    metadata: JSONDict,
    request_source: RequestSource,
    on_bytes: Callable[[bytes], Awaitable[None] | None],
    on_initial_bundle: Callable[[AgentStreamingTaskBundle], Awaitable[None] | None] | None,
    on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None,
    on_inference_payload_prepared: Callable[[JSONDict], Awaitable[None] | None] | None,
    on_compacted_prompt_occupancy: Callable[[PromptOccupancy], None] | None,
    include_usage: bool,
    include_usage_in_result: bool,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    prepared_auto_compaction: PreparedAutoCompactionSnapshot | None,
    turn_id: str | None,
    initial_active_inference_cancellation_id: str | None,
    on_claimed: Callable[[], Awaitable[None] | None] | None,
    operation: str,
    cancelled_log_message: str,
    validate_visible_assistant_output: (
        Callable[[str], Awaitable[PreviewContractOutputValidationResult]] | None
    ) = None,
    initial_output_publication_mode: AgentOutputPublicationMode | None = None,
) -> PreparedStreamingTurnExecution:
    execution: PreparedStreamingTurnExecution | None = None

    async def execute_stream() -> None:
        nonlocal execution
        execution = await execute_prepared_streaming_turn(
            api_dependencies,
            deps=deps,
            context=context,
            tool_context=tool_context,
            requested_model=requested_model,
            settings=settings,
            initial_messages=initial_messages,
            initial_boundary_source_messages=initial_boundary_source_messages,
            base_request_payload=base_request_payload,
            owner_id=owner_id,
            cancellation_id=cancellation_id,
            metadata=metadata,
            request_source=request_source,
            on_bytes=on_bytes,
            on_initial_bundle=on_initial_bundle,
            on_visible_deltas=on_visible_deltas,
            on_inference_payload_prepared=on_inference_payload_prepared,
            on_compacted_prompt_occupancy=on_compacted_prompt_occupancy,
            include_usage=include_usage,
            include_usage_in_result=include_usage_in_result,
            summarize_messages=summarize_messages,
            prepared_auto_compaction=prepared_auto_compaction,
            turn_id=turn_id,
            validate_visible_assistant_output=validate_visible_assistant_output,
            initial_output_publication_mode=initial_output_publication_mode,
        )

    await execute_claimed_stream(
        deps=deps,
        database_agent_turns=api_dependencies.database_agent_turns,
        context=context,
        tool_context=tool_context,
        settings=settings,
        requested_model=requested_model,
        todo_state=todo_state,
        conv_id=tool_context.conv_id,
        user_id=tool_context.user_id,
        initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
        execute_stream=execute_stream,
        on_claimed=on_claimed,
        shutdown_event=api_dependencies.shutdown_event,
        operation=operation,
        cancelled_log_message=cancelled_log_message,
    )
    if execution is None:
        raise ValidationError(
            "Claimed prepared stream execution did not produce an execution result.",
        )
    return execution
