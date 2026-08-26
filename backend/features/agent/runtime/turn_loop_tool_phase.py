"""SoAI - Agent turn-loop tool execution phase [backend/features/agent/runtime/turn_loop_tool_phase.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.tool_calls.conversation_stop_signal import (
    STOP_CONVERSATION_TOOL_NAME,
    is_stop_conversation_signal,
)
from features.agent.runtime.openai_messages import build_post_tool_prompt_messages
from features.agent.runtime.tool_call_execution_support import (
    AgentToolCallExecutionOutcome,
)
from features.agent.runtime.tool_execution import execute_tool_calls_with_agent_events
from features.agent.runtime.tool_image_relay_messages import (
    build_tool_image_relay_message_for_prompt,
)
from features.agent.runtime.tool_phase_execution_context import (
    ToolPhaseExecutionContext,
)
from features.agent.runtime.turn_tool_result_postprocessors import (
    build_turn_tool_result_postprocessor,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.logging.protocols import LoggerProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.tool_calls.tool_result_prompt_cache import ToolResultPromptShapeCache
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ToolPhaseOutcome",
    "append_post_tool_messages",
    "build_persisted_tool_calls",
    "execute_turn_tool_phase",
)


@dataclass(frozen=True, slots=True)
class ToolPhaseOutcome:
    tool_results_count: int
    stop_requested: bool


def build_persisted_tool_calls(
    tool_calls: list[JSONDict],
    tool_outcomes: list[AgentToolCallExecutionOutcome],
) -> list[JSONDict]:
    persisted_tool_calls: list[JSONDict] = []
    used_outcome_indexes: set[int] = set()
    for tool_call in tool_calls:
        persisted_tool_call = dict(tool_call)
        tool_call_id = str(tool_call.get("id") or "").strip()
        if not tool_call_id:
            persisted_tool_calls.append(persisted_tool_call)
            continue
        for outcome_index, tool_outcome in enumerate(tool_outcomes):
            if outcome_index in used_outcome_indexes:
                continue
            outcome_tool_call_id = str(tool_outcome.tool_call_id or "").strip()
            if outcome_tool_call_id != tool_call_id:
                continue
            started_at_ms = tool_outcome.started_at_ms
            duration_ms = tool_outcome.duration_ms
            if started_at_ms >= 0:
                persisted_tool_call["started_at_ms"] = started_at_ms
            if duration_ms >= 0:
                persisted_tool_call["duration_ms"] = duration_ms
            used_outcome_indexes.add(outcome_index)
            break
        persisted_tool_calls.append(persisted_tool_call)
    return persisted_tool_calls


def _has_stop_conversation_outcome(
    tool_outcomes: list[AgentToolCallExecutionOutcome],
) -> bool:
    return any(
        tool_outcome.tool_name == STOP_CONVERSATION_TOOL_NAME
        and is_stop_conversation_signal(tool_outcome.result_payload)
        for tool_outcome in tool_outcomes
    )


async def execute_turn_tool_phase(
    *,
    phase_context: ToolPhaseExecutionContext,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    settings: AgentSettings,
) -> ToolPhaseOutcome:
    prior_tool_results = (
        list(phase_context.turn_state_writer.latest_tool_results)
        if phase_context.request_context.conversation_input_resume_phase is not None
        else []
    )
    completed_tool_count = len(prior_tool_results)
    if completed_tool_count > len(phase_context.tool_calls):
        raise StateError("Persisted tool results exceed persisted tool calls.")

    async def persist_tool_progress(
        current_tool_calls: list[JSONDict],
        current_tool_outcomes: list[AgentToolCallExecutionOutcome],
    ) -> None:
        if current_tool_calls != phase_context.tool_calls[completed_tool_count:]:
            raise StateError("Tool progress call identity changed during execution.")
        await phase_context.turn_state_writer.after_tools(
            iteration_index=phase_context.iteration_index,
            assistant_text=phase_context.assistant_text,
            tool_calls=build_persisted_tool_calls(
                phase_context.tool_calls,
                current_tool_outcomes,
            ),
            tool_results=[
                *prior_tool_results,
                *(outcome.result_payload for outcome in current_tool_outcomes),
            ],
        )

    tool_outcomes = await execute_tool_calls_with_agent_events(
        request_context=phase_context.request_context,
        tool_context=phase_context.tool_context,
        tool_call_processor=phase_context.tool_call_processor,
        database_tool_calls=phase_context.database_tool_calls,
        task_registry=phase_context.task_registry,
        database_notifications=phase_context.database_notifications,
        conversation_attention=phase_context.conversation_attention,
        database_input_queue=phase_context.database_input_queue,
        database_users=phase_context.database_users,
        raw_tool_calls=phase_context.tool_calls[completed_tool_count:],
        message_index=int(phase_context.tool_context.message_index),
        logger=phase_context.logger,
        cancellation_history=phase_context.cancellation_history,
        cancellation_id=phase_context.current_cancellation_id,
        turn_id=phase_context.primitives.turn_id,
        iteration_index=phase_context.iteration_index,
        next_action_sequence=phase_context.sequence_tracker.next_sequence,
        publish_event=phase_context.emit_event,
        deadline_monotonic=None,
        persist_progress=persist_tool_progress,
        postprocess_tool_result=build_turn_tool_result_postprocessor(
            primitives=phase_context.primitives,
            turn_state_writer=phase_context.turn_state_writer,
            next_action_sequence=phase_context.sequence_tracker.next_sequence,
        ),
    )
    if await phase_context.turn_cancelled():
        raise asyncio.CancelledError()
    tool_results: list[JSONValue] = [
        *prior_tool_results,
        *(outcome.result_payload for outcome in tool_outcomes),
    ]
    persisted_tool_calls = build_persisted_tool_calls(
        phase_context.tool_calls,
        tool_outcomes,
    )
    stop_requested = _has_stop_conversation_outcome(tool_outcomes)
    await phase_context.turn_state_writer.after_tools(
        iteration_index=phase_context.iteration_index,
        assistant_text=phase_context.assistant_text,
        tool_calls=persisted_tool_calls,
        tool_results=tool_results,
    )
    if phase_context.task_registry is not None:
        await phase_context.task_registry.database_tasks.consume_interaction_secrets_after_turn_checkpoint(
            turn_id=phase_context.primitives.turn_id,
            iteration_index=phase_context.iteration_index,
        )
    if not stop_requested:
        await append_post_tool_messages(
            message_history=phase_context.message_history,
            boundary_source_messages=phase_context.boundary_source_messages,
            persisted_tool_calls=persisted_tool_calls,
            tool_results=tool_results,
            assistant_text=phase_context.assistant_text,
            logger=phase_context.logger,
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            settings=settings,
            shape_cache=phase_context.shape_cache,
        )
    return ToolPhaseOutcome(
        tool_results_count=len(tool_results),
        stop_requested=stop_requested,
    )


async def append_post_tool_messages(
    *,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    persisted_tool_calls: list[JSONDict],
    tool_results: list[JSONValue],
    assistant_text: str | None,
    logger: LoggerProtocol,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    settings: AgentSettings,
    shape_cache: ToolResultPromptShapeCache,
) -> None:
    post_tool_messages = build_post_tool_prompt_messages(
        tool_calls=persisted_tool_calls,
        tool_results=tool_results,
        assistant_text=assistant_text,
        settings=settings,
        shape_cache=shape_cache,
    )
    prior_history = list(message_history)
    message_history.extend(post_tool_messages)
    boundary_source_messages.extend(dict(message) for message in post_tool_messages)
    if not settings.tool_result_image_relay_enabled:
        return
    relay_message = await build_tool_image_relay_message_for_prompt(
        logger=logger,
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=prior_history,
        pending_messages=post_tool_messages,
        tool_results=tool_results,
        max_prompt_tokens=settings.compaction_trigger_prompt_tokens,
        max_encoded_chars=settings.tool_result_image_relay_max_encoded_chars,
        token_estimation_profile=settings.token_estimation_profile,
        max_pixels=settings.tool_result_image_relay_max_pixels,
    )
    if relay_message is not None:
        message_history.append(relay_message)
        boundary_source_messages.append(dict(relay_message))
