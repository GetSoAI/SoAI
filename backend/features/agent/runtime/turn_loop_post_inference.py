"""SoAI - Agent turn-loop post-inference handling [backend/features/agent/runtime/turn_loop_post_inference.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.tool_call_fields import resolve_tool_call_name
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_required_non_empty_str
from features.agent.runtime.model_output_contract_recovery import (
    payload_hidden_reasoning_contains_tool_call_markup,
)
from features.agent.runtime.openai_messages import build_post_tool_prompt_messages
from features.agent.runtime.openai_payload import (
    remove_length_truncated_assistant_tool_calls,
    remove_rejected_assistant_tool_calls,
)
from features.agent.runtime.tool_call_protocol_events import (
    publish_rejected_tool_call_events,
)
from features.agent.runtime.tool_call_protocol_policy import (
    decide_tool_call_protocol_action,
)
from features.agent.runtime.tool_call_protocol_validation import (
    validate_tool_call_protocol,
)
from features.agent.runtime.turn_iteration_policy import decide_post_inference_action
from features.agent.runtime.turn_iteration_policy_types import (
    FINISH_REASON_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION,
)
from features.agent.runtime.turn_loop_retry_messages import append_turn_retry_message
from features.agent.runtime.turn_loop_tool_sequences import resolve_turn_loop_tool_calls

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.agent.turn_state_writer import TurnStateWriter
    from core.events.types_base import Event
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.tool_calls.tool_result_prompt_cache import ToolResultPromptShapeCache
    from core.types.json import JSONDict, JSONValue
    from features.agent.runtime.turn_engine import TurnPrimitives
    from features.agent.runtime.turn_iteration_policy_types import (
        AgentOutputPublicationMode,
        TurnIterationDecision,
        TurnIterationPolicyConfig,
        TurnIterationPolicyState,
    )
    from features.agent.runtime.turn_loop_tool_sequences import (
        TurnLoopToolSequenceState,
    )
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = (
    "TurnLoopPostInferenceOutcome",
    "resolve_turn_loop_post_inference",
)


@dataclass(frozen=True, slots=True)
class TurnLoopPostInferenceOutcome:
    assistant_text: str | None
    assistant_output_published: bool
    tool_calls: list[JSONDict]
    decision: TurnIterationDecision
    next_policy_state: TurnIterationPolicyState


def _build_orphaned_detected_tool_rejections(
    *,
    detected_tool_calls: list[JSONDict],
    accepted_tool_calls: list[JSONDict],
) -> tuple[list[JSONDict], list[JSONValue]]:
    accepted_call_ids = {
        str(tool_call.get("id") or "").strip()
        for tool_call in accepted_tool_calls
        if str(tool_call.get("id") or "").strip()
    }
    rejected_calls: list[JSONDict] = []
    rejected_results: list[JSONValue] = []
    for detected_tool_call in detected_tool_calls:
        call_id = str(detected_tool_call.get("id") or "").strip()
        if not call_id or call_id in accepted_call_ids:
            continue
        tool_name = coerce_required_non_empty_str(
            resolve_tool_call_name(detected_tool_call),
            label="Detected tool call name",
        )
        rejected_call: JSONDict = {
            "id": call_id,
            "name": tool_name,
            "arguments": {},
        }
        for field_name in (
            "sequence_index",
            "content_index_before",
            "thinking_index_before",
            "thinking_duration_before_ms",
        ):
            field_value = detected_tool_call.get(field_name)
            if is_strict_int(field_value) and field_value >= 0:
                rejected_call[field_name] = field_value
        rejected_calls.append(rejected_call)
        rejected_results.append(
            {
                "error": "The streamed tool call did not produce an executable final call.",
                "code": "streamed_tool_call_not_executable",
                "tool_name": rejected_call["name"],
                "raw_arguments_omitted": True,
            },
        )
    return rejected_calls, rejected_results


async def resolve_turn_loop_post_inference(
    *,
    final_payload: JSONDict,
    assistant_text: str | None,
    assistant_output_published: bool,
    current_inference_tool_calls: list[JSONDict],
    current_inference_detected_tool_calls: list[JSONDict],
    current_inference_visible_text_chars: int,
    current_inference_thinking_text_chars: int,
    finish_reason: str | None,
    output_publication_mode: AgentOutputPublicationMode,
    iteration_index: int,
    tool_sequence_state: TurnLoopToolSequenceState,
    turn_state_writer: TurnStateWriter,
    tool_context: MCPToolContext,
    request_context: RequestContext,
    primitives: TurnPrimitives,
    settings: AgentSettings,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    iteration_policy_state: TurnIterationPolicyState,
    iteration_policy_config: TurnIterationPolicyConfig,
    next_action_sequence: Callable[[], Awaitable[int]],
    emit_event: Callable[[Event], Awaitable[None]],
    database_tool_calls: DatabaseToolCallsProtocol,
    shape_cache: ToolResultPromptShapeCache,
    validate_visible_assistant_output: (
        Callable[
            [str],
            Awaitable[PreviewContractOutputValidationResult],
        ]
        | None
    ),
) -> TurnLoopPostInferenceOutcome:
    resolved_assistant_text, preview_contract_validation, tool_calls = (
        await resolve_turn_loop_tool_calls(
            final_payload=final_payload,
            assistant_text=assistant_text,
            assistant_output_published=assistant_output_published,
            resolved_tool_calls=current_inference_tool_calls,
            visible_text_chars=current_inference_visible_text_chars,
            thinking_text_chars=current_inference_thinking_text_chars,
            tool_sequence_state=tool_sequence_state,
            offered_tool_names=frozenset(tool_context.tool_map.keys()),
            validate_visible_assistant_output=validate_visible_assistant_output,
        )
    )
    tool_sequence_state.reserve_detected_tool_calls(current_inference_detected_tool_calls)
    if (
        not tool_calls
        and not str(resolved_assistant_text or "").strip()
        and tool_context.tool_map
        and payload_hidden_reasoning_contains_tool_call_markup(final_payload)
    ):
        finish_reason = FINISH_REASON_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION
    if (
        finish_reason == "length"
        and not iteration_policy_config.length_finish_reason_retries_enabled
    ):
        remove_length_truncated_assistant_tool_calls(final_payload)
        tool_calls = []
    orphaned_calls, orphaned_results = _build_orphaned_detected_tool_rejections(
        detected_tool_calls=current_inference_detected_tool_calls,
        accepted_tool_calls=tool_calls,
    )
    if orphaned_calls:
        await publish_rejected_tool_call_events(
            prompt_tool_calls=orphaned_calls,
            prompt_tool_results=orphaned_results,
            tool_context=tool_context,
            primitives=primitives,
            iteration_index=iteration_index,
            turn_state_writer=turn_state_writer,
            next_action_sequence=next_action_sequence,
            emit_event=emit_event,
            database_tool_calls=database_tool_calls,
            request_context=request_context,
        )
    published_assistant_text = resolved_assistant_text if assistant_output_published else None
    violation = validate_tool_call_protocol(
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        available_tool_map=tool_context.tool_map,
    )
    if violation is not None:
        remove_rejected_assistant_tool_calls(final_payload)
        await publish_rejected_tool_call_events(
            prompt_tool_calls=violation.prompt_tool_calls,
            prompt_tool_results=violation.prompt_tool_results,
            tool_context=tool_context,
            primitives=primitives,
            iteration_index=iteration_index,
            turn_state_writer=turn_state_writer,
            next_action_sequence=next_action_sequence,
            emit_event=emit_event,
            database_tool_calls=database_tool_calls,
            request_context=request_context,
        )
        await turn_state_writer.after_tools(
            iteration_index=iteration_index,
            assistant_text=published_assistant_text,
            tool_calls=violation.prompt_tool_calls,
            tool_results=violation.prompt_tool_results,
        )
        decision = decide_tool_call_protocol_action(
            config=iteration_policy_config,
            state=iteration_policy_state,
            iteration_index=iteration_index,
            violation=violation,
            output_publication_mode=output_publication_mode,
        )
        post_tool_messages = build_post_tool_prompt_messages(
            tool_calls=violation.prompt_tool_calls,
            tool_results=violation.prompt_tool_results,
            assistant_text=published_assistant_text,
            settings=settings,
            shape_cache=shape_cache,
        )
        message_history.extend(post_tool_messages)
        boundary_source_messages.extend(dict(message) for message in post_tool_messages)
        if decision.retry_message is not None:
            message_history.append(decision.retry_message)
            boundary_source_messages.append(dict(decision.retry_message))
        return TurnLoopPostInferenceOutcome(
            assistant_text=resolved_assistant_text,
            assistant_output_published=assistant_output_published,
            tool_calls=[],
            decision=decision,
            next_policy_state=decision.next_state,
        )
    await turn_state_writer.after_inference(
        iteration_index,
        published_assistant_text,
        tool_calls,
    )
    decision = decide_post_inference_action(
        config=iteration_policy_config,
        state=iteration_policy_state,
        iteration_index=iteration_index,
        tool_calls=tool_calls,
        assistant_text=resolved_assistant_text,
        finish_reason=finish_reason,
        preview_contract_validation=preview_contract_validation,
        current_output_publication_mode=output_publication_mode,
    )
    if decision.retry_message is not None:
        append_turn_retry_message(
            message_history=message_history,
            boundary_source_messages=boundary_source_messages,
            assistant_text=published_assistant_text,
            retry_message=decision.retry_message,
        )
    return TurnLoopPostInferenceOutcome(
        assistant_text=resolved_assistant_text,
        assistant_output_published=assistant_output_published,
        tool_calls=tool_calls,
        decision=decision,
        next_policy_state=decision.next_state,
    )
