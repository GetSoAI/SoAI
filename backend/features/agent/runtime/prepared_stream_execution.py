"""SoAI - Shared prepared streaming turn execution [backend/features/agent/runtime/prepared_stream_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.settings_types import AgentSettings
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from features.agent.runtime.streaming_inference_admission import (
    AgentStreamingTaskBundle,
    create_streaming_inference_task,
)
from features.agent.runtime.streaming_inference_runner_callbacks import (
    build_agent_streaming_inference_runner,
)
from features.agent.runtime.streaming_turn_engine import run_streaming_turn
from features.agent.runtime.turn_engine import (
    AgentTurnEngineDependencies,
    AgentTurnResult,
)
from features.agent.runtime.turn_iteration_policy_types import AgentOutputPublicationMode

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.activity_result import (
        PreparedAutoCompactionSnapshot,
    )
    from features.api.runtime.container.types import ApiDependencies
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = (
    "AgentStreamingTaskBundle",
    "PreparedStreamingTurnExecution",
    "execute_prepared_streaming_turn",
)


@dataclass(frozen=True, slots=True)
class PreparedStreamingTurnExecution:
    initial_bundle: AgentStreamingTaskBundle | None
    result: AgentTurnResult


async def execute_prepared_streaming_turn(
    api_dependencies: ApiDependencies,
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    requested_model: str | None,
    settings: AgentSettings,
    initial_messages: list[JSONDict],
    initial_boundary_source_messages: list[JSONDict],
    base_request_payload: JSONDict,
    owner_id: str,
    cancellation_id: str,
    metadata: JSONDict,
    request_source: RequestSource,
    on_bytes: Callable[[bytes], Awaitable[None] | None],
    include_usage: bool,
    include_usage_in_result: bool,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    prepared_auto_compaction: PreparedAutoCompactionSnapshot | None,
    turn_id: str | None,
    on_initial_bundle: Callable[[AgentStreamingTaskBundle], Awaitable[None] | None] | None = None,
    on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None = None,
    on_inference_payload_prepared: Callable[[JSONDict], Awaitable[None] | None] | None = None,
    on_compacted_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
    validate_visible_assistant_output: (
        Callable[[str], Awaitable[PreviewContractOutputValidationResult]] | None
    ) = None,
    initial_output_publication_mode: AgentOutputPublicationMode | None = None,
) -> PreparedStreamingTurnExecution:
    initial_bundle: AgentStreamingTaskBundle | None = None
    if context.conversation_input_resume_phase is None:
        initial_bundle = await create_streaming_inference_task(
            api_dependencies,
            context=context,
            request_json=base_request_payload,
            task_type=TASK_TYPE_CHAT_COMPLETION,
            user_id=int(context.user_id),
            owner_type="conversation",
            owner_id=owner_id,
            cancellation_id=cancellation_id,
            metadata=metadata,
            request_source=request_source,
        )
    if on_initial_bundle is not None and initial_bundle is not None:
        initial_bundle_awaitable = on_initial_bundle(initial_bundle)
        if initial_bundle_awaitable is not None:
            await initial_bundle_awaitable
    runner = build_agent_streaming_inference_runner(
        api_dependencies,
        context=context,
        initial_task=initial_bundle.task if initial_bundle is not None else None,
        initial_reply_queue=initial_bundle.reply_queue if initial_bundle is not None else None,
        task_type=TASK_TYPE_CHAT_COMPLETION,
        user_id=int(context.user_id),
        owner_type="conversation",
        owner_id=owner_id,
        metadata=metadata,
        model=requested_model,
        request_source=request_source,
        token_estimation_profile=settings.token_estimation_profile,
    )
    result = await run_streaming_turn(
        deps=deps,
        context=context,
        tool_context=tool_context,
        initial_messages=initial_messages,
        initial_boundary_source_messages=initial_boundary_source_messages,
        base_request_payload=(
            dict(initial_bundle.payload)
            if initial_bundle is not None
            else dict(base_request_payload)
        ),
        settings=settings,
        streaming_inference_runner=runner,
        on_bytes=on_bytes,
        on_visible_deltas=on_visible_deltas,
        on_inference_payload_prepared=on_inference_payload_prepared,
        on_compacted_prompt_occupancy=on_compacted_prompt_occupancy,
        include_usage=include_usage,
        summarize_messages=summarize_messages,
        include_usage_in_result=include_usage_in_result,
        first_iteration_cancellation_id=(
            initial_bundle.task.cancellation_id if initial_bundle is not None else None
        ),
        prepared_auto_compaction=prepared_auto_compaction,
        turn_id=turn_id,
        validate_visible_assistant_output=validate_visible_assistant_output,
        initial_output_publication_mode=initial_output_publication_mode,
    )
    return PreparedStreamingTurnExecution(initial_bundle=initial_bundle, result=result)
