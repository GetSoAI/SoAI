"""SoAI - Agent streaming turn engine [backend/features/agent/runtime/streaming_turn_engine.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.agent.tool_call_fields import resolve_tool_call_name
from core.events.types_conversation import ToolCallCreatedEvent
from core.tool_calls.chronology import resolve_required_non_negative_integer
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from core.validation.strings import coerce_required_non_empty_str
from features.agent.runtime.inference_request_payload import (
    build_turn_inference_request_payload_for_iteration,
)
from features.agent.runtime.openai_payload import (
    extract_finish_reason,
)
from features.agent.runtime.streaming_inference_step import stream_inference_step
from features.agent.runtime.streaming_turn_completion import (
    emit_streaming_turn_completion,
)
from features.agent.runtime.streaming_usage_resolution import (
    resolve_streaming_step_usage,
)
from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
)
from features.agent.runtime.turn_loop_models import TurnLoopInferenceResult
from features.agent.runtime.turn_runtime_execution import execute_agent_turn_runtime

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.openai.token_accounting import PromptOccupancy
    from core.openai.usage.models import CanonicalUsage
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.agent.internal_protocols import AgentStreamingInferenceRunnerProtocol
    from features.agent.runtime.context_compaction.activity_result import (
        PreparedAutoCompactionSnapshot,
    )
    from features.agent.runtime.tool_sequence_reservations import (
        ToolSequenceIndexReservation,
    )
    from features.agent.runtime.turn_bootstrap import AgentTurnBootstrap
    from features.agent.runtime.turn_engine import (
        AgentTurnEngineDependencies,
        AgentTurnResult,
    )
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = ("run_streaming_turn",)


async def run_streaming_turn(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    initial_messages: list[JSONDict],
    initial_boundary_source_messages: list[JSONDict],
    base_request_payload: JSONDict,
    settings: AgentSettings,
    streaming_inference_runner: AgentStreamingInferenceRunnerProtocol,
    on_bytes: Callable[[bytes], Awaitable[None] | None],
    on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None = None,
    on_inference_payload_prepared: Callable[[JSONDict], Awaitable[None] | None] | None = None,
    on_pre_compaction_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
    on_compacted_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
    on_visible_usage_resolved: Callable[[CanonicalUsage], Awaitable[None] | None] | None = None,
    include_usage: bool,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    include_usage_in_result: bool = False,
    first_iteration_cancellation_id: str | None = None,
    prepared_auto_compaction: PreparedAutoCompactionSnapshot | None = None,
    turn_id: str | None = None,
    validate_visible_assistant_output: (
        Callable[
            [str],
            Awaitable[PreviewContractOutputValidationResult],
        ]
        | None
    ) = None,
    initial_output_publication_mode: AgentOutputPublicationMode | None = None,
) -> AgentTurnResult:
    def reserve_streaming_tool_sequence_indexes(
        reservation: ToolSequenceIndexReservation,
    ) -> None:
        streaming_inference_runner.reserve_tool_sequence_indexes(reservation.streaming_offset_count)

    async def run_inference(
        iteration_index: int,
        cancellation_id: str,
        current_history: list[JSONDict],
        suppress_tools: bool,
        output_publication_mode: AgentOutputPublicationMode,
        bootstrap: AgentTurnBootstrap,
    ) -> TurnLoopInferenceResult:
        request_payload = await build_turn_inference_request_payload_for_iteration(
            deps=deps,
            context=context,
            bootstrap=bootstrap,
            base_request_payload=base_request_payload,
            current_history=current_history,
            suppress_tools=suppress_tools,
        )
        if on_inference_payload_prepared is not None:
            prepared_awaitable = on_inference_payload_prepared(request_payload)
            if prepared_awaitable is not None:
                await prepared_awaitable

        async def publish_detected_tool_calls(tool_calls: tuple[JSONDict, ...]) -> None:
            for tool_call in tool_calls:
                await bootstrap.emit_event(
                    ToolCallCreatedEvent(
                        user_id=bootstrap.primitives.user_id,
                        conv_id=bootstrap.primitives.conv_id,
                        call_id=coerce_required_non_empty_str(
                            tool_call.get("id"),
                            label="Streamed tool call id",
                        ),
                        tool_name=coerce_required_non_empty_str(
                            resolve_tool_call_name(tool_call),
                            label="Streamed tool call name",
                        ),
                        message_index=int(tool_context.message_index),
                        sequence_index=resolve_required_non_negative_integer(
                            tool_call.get("sequence_index"),
                            "sequence_index",
                            field_label="Streamed tool call",
                        ),
                        content_index_before=resolve_required_non_negative_integer(
                            tool_call.get("content_index_before"),
                            "content_index_before",
                            field_label="Streamed tool call",
                        ),
                        thinking_index_before=resolve_required_non_negative_integer(
                            tool_call.get("thinking_index_before"),
                            "thinking_index_before",
                            field_label="Streamed tool call",
                        ),
                        thinking_duration_before_ms=coerce_optional_non_negative_int_strict(
                            tool_call.get("thinking_duration_before_ms"),
                        ),
                        tool_arguments=None,
                        turn_id=bootstrap.primitives.turn_id,
                        iteration_index=iteration_index,
                    ),
                )

        step_result = await stream_inference_step(
            event_bus=deps.event_bus,
            logger=deps.logger,
            conv_id=bootstrap.primitives.conv_id,
            user_id=bootstrap.primitives.user_id,
            turn_id=bootstrap.primitives.turn_id,
            iteration_index=iteration_index,
            cancellation_id=cancellation_id,
            payload=request_payload,
            streaming_inference_runner=streaming_inference_runner,
            next_action_sequence=bootstrap.sequence_tracker.next_sequence,
            on_bytes=on_bytes,
            on_visible_deltas=on_visible_deltas,
            validate_buffered_output=validate_visible_assistant_output,
            output_publication_mode=output_publication_mode,
            on_tool_calls_detected=publish_detected_tool_calls,
            suppress_tools=suppress_tools,
        )
        outcome = step_result.outcome
        assistant_text = step_result.assistant_text
        resolved_tool_calls = [dict(tool_call) for tool_call in outcome.tool_calls]
        resolved_visible_text_chars = outcome.visible_text_chars
        resolved_thinking_text_chars = outcome.thinking_text_chars
        if not step_result.assistant_output_published:
            resolved_tool_calls = []
            resolved_visible_text_chars = 0
            resolved_thinking_text_chars = 0
        step_usage = await resolve_streaming_step_usage(
            prompt_token_counter=deps.prompt_token_counter,
            request_payload=request_payload,
            outcome=outcome,
            token_estimation_profile=bootstrap.settings.token_estimation_profile,
        )
        if step_usage is not None and step_result.assistant_output_published:
            if on_visible_usage_resolved is not None:
                usage_awaitable = on_visible_usage_resolved(step_usage)
                if usage_awaitable is not None:
                    await usage_awaitable
        return TurnLoopInferenceResult(
            payload=outcome.payload,
            assistant_text=assistant_text,
            finish_reason=extract_finish_reason(outcome.payload) if outcome.payload else None,
            usage=step_usage,
            stream_id=outcome.stream_id,
            successful=bool(outcome.stream_successful),
            error_message=outcome.error_message,
            error_type=outcome.error_type,
            error_details=None,
            assistant_output_published=step_result.assistant_output_published,
            tool_calls=resolved_tool_calls,
            detected_tool_calls=[dict(tool_call) for tool_call in step_result.detected_tool_calls],
            visible_text_chars=resolved_visible_text_chars,
            thinking_text_chars=resolved_thinking_text_chars,
        )

    runtime_execution = await execute_agent_turn_runtime(
        deps=deps,
        context=context,
        tool_context=tool_context,
        turn_id=turn_id,
        initial_active_inference_cancellation_id=first_iteration_cancellation_id,
        initial_messages=initial_messages,
        initial_boundary_source_messages=initial_boundary_source_messages,
        settings=settings,
        base_request_payload=base_request_payload,
        summarize_messages=summarize_messages,
        prepared_auto_compaction=prepared_auto_compaction,
        run_inference=run_inference,
        operation="agent.streaming_turn.run_streaming_turn",
        include_usage_in_result=include_usage_in_result,
        on_tool_sequence_indexes_reserved=reserve_streaming_tool_sequence_indexes,
        on_pre_compaction_prompt_occupancy=on_pre_compaction_prompt_occupancy,
        on_compacted_prompt_occupancy=on_compacted_prompt_occupancy,
        validate_visible_assistant_output=validate_visible_assistant_output,
        initial_output_publication_mode=(
            initial_output_publication_mode or AgentOutputPublicationMode.STREAM_LIVE
        ),
    )
    await emit_streaming_turn_completion(
        include_usage=include_usage,
        usage_aggregate=runtime_execution.usage_aggregate,
        stream_id=runtime_execution.stream_id,
        base_request_payload=base_request_payload,
        on_bytes=on_bytes,
    )
    return runtime_execution.result
