"""SoAI - Agent streaming inference step runner [backend/features/agent/runtime/streaming_inference_step.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.openai.internal_retry_prompt import is_internal_retry_output_leak
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.tool_calls.chronology import bound_required_chronology_anchor
from core.validation.integers import is_strict_int
from features.agent.internal_protocols import (
    AgentStreamingInferenceOutcome,
    AgentStreamingInferenceRunnerProtocol,
)
from features.agent.runtime.injected_prompt_echo_stripping import (
    strip_echoed_injected_prompt_blocks,
)
from features.agent.runtime.item_event_factories import (
    build_agent_assistant_item_completed_event,
)
from features.agent.runtime.model_output_contract_recovery import (
    is_invalid_tool_call_json_outcome,
    recover_streaming_invalid_tool_call_json_outcome,
)
from features.agent.runtime.openai_payload import (
    extract_assistant_content_visible,
    remove_suppressed_assistant_tool_calls,
    replace_assistant_content_visible,
)
from features.agent.runtime.streaming_assistant_output_publisher import (
    StreamingAssistantOutputPublisher,
)
from features.agent.runtime.streaming_inference_outcomes import (
    build_agent_streaming_inference_outcome,
)
from features.agent.runtime.streaming_inference_runner import (
    INFERENCE_ADMISSION_UNAVAILABLE_ERROR_TYPE,
    StreamingTaskCreationRetryableError,
)
from features.agent.runtime.turn_engine import publish_agent_event
from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.agent.internal_protocols import AgentToolCallsDetectedCallback
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = ("StreamingInferenceStepResult", "stream_inference_step")


@dataclass(frozen=True, slots=True)
class StreamingInferenceStepResult:
    outcome: AgentStreamingInferenceOutcome
    assistant_text: str
    assistant_output_published: bool
    detected_tool_calls: list[JSONDict]


async def stream_inference_step(
    *,
    event_bus: EventBusProtocol | None,
    logger: LoggerProtocol,
    conv_id: str,
    user_id: int,
    turn_id: str,
    iteration_index: int,
    cancellation_id: str,
    payload: JSONDict,
    streaming_inference_runner: AgentStreamingInferenceRunnerProtocol,
    next_action_sequence: Callable[[], Awaitable[int]],
    on_bytes: Callable[[bytes], Awaitable[None] | None],
    output_publication_mode: AgentOutputPublicationMode,
    on_tool_calls_detected: AgentToolCallsDetectedCallback | None = None,
    on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None = None,
    validate_buffered_output: (
        Callable[[str], Awaitable[PreviewContractOutputValidationResult]] | None
    ) = None,
    suppress_tools: bool = False,
) -> StreamingInferenceStepResult:
    item_id = create_prefixed_hex_id("item", length=12)
    buffer_output = output_publication_mode is AgentOutputPublicationMode.VALIDATE_BEFORE_PUBLISH
    output_publisher = StreamingAssistantOutputPublisher(
        event_bus=event_bus,
        logger=logger,
        payload=payload,
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        item_id=item_id,
        iteration_index=iteration_index,
        buffer_output=buffer_output,
        next_action_sequence=next_action_sequence,
        on_bytes=on_bytes,
        on_visible_deltas=on_visible_deltas,
    )

    if not buffer_output:
        await output_publisher.publish_item_started_event()

    detected_tool_calls: list[JSONDict] = []

    async def record_detected_tool_calls(tool_calls: tuple[JSONDict, ...]) -> None:
        detected_tool_calls.extend(dict(tool_call) for tool_call in tool_calls)
        if buffer_output or on_tool_calls_detected is None:
            return
        detected_awaitable = on_tool_calls_detected(tool_calls)
        if detected_awaitable is not None:
            await detected_awaitable

    try:
        outcome = await streaming_inference_runner(
            payload,
            iteration_index=iteration_index,
            cancellation_id=cancellation_id,
            on_bytes=output_publisher.handle_bytes,
            on_visible_deltas=output_publisher.handle_visible_deltas,
            on_tool_calls_detected=record_detected_tool_calls,
        )
    except StreamingTaskCreationRetryableError as exception:
        logger.warning(
            "Agent streaming inference admission unavailable; surfacing retryable failure (error_type=%s).",
            exception.error_type,
        )
        streaming_inference_runner.discard_latest_iteration()
        if not buffer_output:
            await publish_agent_event(
                event_bus=event_bus,
                logger=logger,
                event_obj=build_agent_assistant_item_completed_event(
                    user_id=user_id,
                    conv_id=conv_id,
                    turn_id=turn_id,
                    item_id=item_id,
                    iteration_index=iteration_index,
                    sequence=await next_action_sequence(),
                    final_text="",
                ),
            )
        return StreamingInferenceStepResult(
            outcome=build_agent_streaming_inference_outcome(
                payload=None,
                stream_successful=False,
                done_sent=False,
                error_message=exception.error_message or "Inference admission unavailable.",
                error_type=INFERENCE_ADMISSION_UNAVAILABLE_ERROR_TYPE,
            ),
            assistant_text="",
            assistant_output_published=False,
            detected_tool_calls=[],
        )
    final_text = ""
    if outcome.payload is not None:
        final_text = extract_assistant_content_visible(outcome.payload)
    if not final_text:
        final_text = output_publisher.buffered_text()
    stripping = strip_echoed_injected_prompt_blocks(final_text)
    retry_output_leaked = False
    if stripping.stripped:
        logger.warning(
            "Stripped injected prompt echo from assistant output (tags=%s, removed_chars=%d).",
            ",".join(stripping.stripped_tags),
            max(0, len(final_text) - len(stripping.sanitized_text)),
        )
        final_text = stripping.sanitized_text
        retry_output_leaked = buffer_output
    if buffer_output and is_internal_retry_output_leak(final_text):
        logger.warning("Suppressed internal retry prompt leak from assistant output.")
        final_text = ""
        retry_output_leaked = True
    if outcome.payload is not None:
        replace_assistant_content_visible(outcome.payload, final_text)
    invalid_tool_call_json_recovered = is_invalid_tool_call_json_outcome(
        error_message=outcome.error_message,
        error_type=outcome.error_type,
    )
    outcome = recover_streaming_invalid_tool_call_json_outcome(
        outcome=outcome,
    )
    if invalid_tool_call_json_recovered:
        final_text = extract_assistant_content_visible(outcome.payload) if outcome.payload else ""
    buffered_output_publishable = not buffer_output or (
        outcome.stream_successful
        and not retry_output_leaked
        and not invalid_tool_call_json_recovered
        and bool(final_text.strip())
    )
    flush_buffered_output = False
    if (
        buffer_output
        and outcome.stream_successful
        and final_text.strip()
        and not retry_output_leaked
        and not invalid_tool_call_json_recovered
    ):
        if validate_buffered_output is not None:
            original_final_text = final_text
            validation = await validate_buffered_output(final_text)
            buffered_output_publishable = validation.compliant
            if validation.compliant:
                final_text = validation.resolved_text
                if outcome.payload is not None:
                    replace_assistant_content_visible(outcome.payload, final_text)
                if final_text.strip():
                    flush_buffered_output = (
                        validation.resolved_text == original_final_text
                        and output_publisher.has_buffered_chunks()
                        and output_publisher.buffered_text_equals(final_text)
                    )
                else:
                    buffered_output_publishable = False
        else:
            flush_buffered_output = (
                output_publisher.has_buffered_chunks()
                and output_publisher.buffered_text_equals(final_text)
            )
        if flush_buffered_output:
            await output_publisher.publish_item_started_event()
            await output_publisher.flush_buffered_output()
        elif buffered_output_publishable:
            await output_publisher.publish_item_started_event()
            repaired_stream_id = await output_publisher.publish_repaired_output(
                final_text,
                outcome.stream_id,
            )
            if outcome.stream_id != repaired_stream_id:
                outcome = replace(outcome, stream_id=repaired_stream_id)
    outcome = _align_outcome_to_final_visible_text(outcome, final_text)
    assistant_output_published = not buffer_output or buffered_output_publishable
    if (suppress_tools or not assistant_output_published) and outcome.payload is not None:
        remove_suppressed_assistant_tool_calls(outcome.payload, assistant_text=final_text)
        outcome = replace(outcome, tool_calls=[])
    if assistant_output_published:
        streaming_inference_runner.commit_latest_iteration(
            visible_text_chars=outcome.visible_text_chars,
            thinking_text_chars=outcome.thinking_text_chars,
            tool_calls=(detected_tool_calls or outcome.tool_calls),
        )
    else:
        streaming_inference_runner.discard_latest_iteration()
    if outcome.payload is not None and outcome.stream_successful:
        if assistant_output_published:
            await publish_agent_event(
                event_bus=event_bus,
                logger=logger,
                event_obj=build_agent_assistant_item_completed_event(
                    user_id=user_id,
                    conv_id=conv_id,
                    turn_id=turn_id,
                    item_id=item_id,
                    iteration_index=iteration_index,
                    sequence=await next_action_sequence(),
                    final_text=final_text,
                ),
            )
    return StreamingInferenceStepResult(
        outcome=outcome,
        assistant_text=final_text,
        assistant_output_published=assistant_output_published,
        detected_tool_calls=(detected_tool_calls if not buffer_output else []),
    )


def _align_outcome_to_final_visible_text(
    outcome: AgentStreamingInferenceOutcome,
    final_text: str,
) -> AgentStreamingInferenceOutcome:
    visible_text_chars = len(final_text)
    if not outcome.tool_calls and outcome.visible_text_chars == visible_text_chars:
        return outcome
    content_upper_bound = outcome.content_index_base + visible_text_chars
    aligned_tool_calls: list[JSONDict] = []
    changed = outcome.visible_text_chars != visible_text_chars
    for tool_call in outcome.tool_calls:
        aligned_tool_call = dict(tool_call)
        content_index_before = aligned_tool_call.get("content_index_before")
        if is_strict_int(content_index_before):
            bounded_content_index_before = bound_required_chronology_anchor(
                content_index_before,
                "content_index_before",
                upper_bound=content_upper_bound,
            )
            if bounded_content_index_before != content_index_before:
                aligned_tool_call["content_index_before"] = bounded_content_index_before
                changed = True
        aligned_tool_calls.append(aligned_tool_call)
    if not changed:
        return outcome
    return replace(
        outcome,
        tool_calls=aligned_tool_calls,
        visible_text_chars=visible_text_chars,
    )
