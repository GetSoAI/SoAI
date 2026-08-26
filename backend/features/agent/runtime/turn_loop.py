"""SoAI - Shared agent turn iteration loop [backend/features/agent/runtime/turn_loop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.tool_calls.tool_result_prompt_cache import ToolResultPromptShapeCache
from features.agent.runtime.tool_phase_execution_context import (
    ToolPhaseExecutionContext,
)
from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
    PostInferenceControl,
)
from features.agent.runtime.turn_loop_checkpoint_resume import (
    resolve_resumed_tool_phase,
)
from features.agent.runtime.turn_loop_compaction_transition import (
    advance_retry_after_compaction,
)
from features.agent.runtime.turn_loop_failed_inference import resolve_failed_inference_transition
from features.agent.runtime.turn_loop_inference_start import start_turn_loop_inference
from features.agent.runtime.turn_loop_models import TurnLoopInferenceResult, TurnLoopResult
from features.agent.runtime.turn_loop_outcome import TurnLoopOutcome
from features.agent.runtime.turn_loop_post_inference import (
    resolve_turn_loop_post_inference,
)
from features.agent.runtime.turn_loop_terminal_outcomes import (
    resolve_post_inference_terminal_outcome,
)
from features.agent.runtime.turn_loop_tool_transition import (
    advance_turn_loop_after_tools,
)
from features.agent.runtime.turn_terminal_state import (
    build_cancelled_turn_terminal_outcome,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.agent.turn_state_writer import TurnStateWriter
    from core.conversations.protocols_database_conversation_inputs import (
        DatabaseConversationInputsProtocol,
    )
    from core.events.types_base import Event
    from core.logging.protocols import LoggerProtocol
    from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import CancellationHistoryProtocol
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tool_calls.protocols import (
        DatabaseToolCallsProtocol,
        ToolCallProcessingProtocol,
    )
    from core.types.json import JSONDict
    from core.users.protocols_database import DatabaseUsersProtocol
    from features.agent.runtime.turn_engine import (
        ActionSequenceTracker,
        AgentTurnTodoState,
        TurnPrimitives,
    )
    from features.agent.runtime.turn_iteration_policy_types import (
        TurnIterationPolicyConfig,
        TurnIterationPolicyState,
    )
    from features.agent.runtime.turn_loop_models import (
        TurnLoopCompactionCallback,
        TurnLoopRunInferenceCallback,
        TurnLoopVisibleAssistantValidator,
    )
    from features.agent.runtime.turn_loop_tool_sequences import (
        TurnLoopToolSequenceState,
    )

__all__ = ("execute_turn_loop",)


async def execute_turn_loop(
    *,
    request_context: RequestContext,
    tool_context: MCPToolContext,
    tool_call_processor: ToolCallProcessingProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task_registry: TaskRegistryProtocol | None,
    database_notifications: DatabaseNotificationsProtocol,
    conversation_attention: ConversationAttentionCoordinatorProtocol,
    database_input_queue: DatabaseConversationInputsProtocol,
    database_users: DatabaseUsersProtocol | None,
    logger: LoggerProtocol,
    cancellation_history: CancellationHistoryProtocol | None,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    settings: AgentSettings,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    todo_state: AgentTurnTodoState,
    primitives: TurnPrimitives,
    sequence_tracker: ActionSequenceTracker,
    tool_sequence_state: TurnLoopToolSequenceState,
    turn_state_writer: TurnStateWriter,
    emit_event: Callable[[Event], Awaitable[None]],
    turn_cancelled: Callable[[], Awaitable[bool]],
    iteration_policy_state: TurnIterationPolicyState,
    iteration_policy_config: TurnIterationPolicyConfig,
    compact_messages: TurnLoopCompactionCallback,
    run_inference: TurnLoopRunInferenceCallback,
    validate_visible_assistant_output: TurnLoopVisibleAssistantValidator,
    initial_output_publication_mode: AgentOutputPublicationMode,
) -> TurnLoopResult:
    iteration_index = 0
    total_tool_calls = 0
    outcome = TurnLoopOutcome()
    current_inference: TurnLoopInferenceResult | None = None
    current_cancellation_id = primitives.base_cancellation_id
    relay_retry_attempted = False
    inference_admission_retries = 0
    suppress_tools_for_next_inference = False
    output_publication_mode = initial_output_publication_mode
    shape_cache = ToolResultPromptShapeCache()
    resumed_tool_phase = resolve_resumed_tool_phase(
        request_context=request_context,
        turn_state_writer=turn_state_writer,
        primitives=primitives,
        settings=settings,
    )
    assistant_text: str | None = None
    tool_calls: list[JSONDict] = []
    execute_tool_phase = resumed_tool_phase is not None
    if resumed_tool_phase is not None:
        iteration_index = resumed_tool_phase.iteration_index
        current_cancellation_id = resumed_tool_phase.cancellation_id
        assistant_text = resumed_tool_phase.assistant_text
        tool_calls = resumed_tool_phase.tool_calls
        outcome.final_text = assistant_text
    while True:
        if await turn_cancelled():
            outcome.terminal_outcome = build_cancelled_turn_terminal_outcome()
            break
        if not execute_tool_phase:
            if current_inference is None:
                current_cancellation_id, current_inference = await start_turn_loop_inference(
                    turn_state_writer=turn_state_writer,
                    iteration_index=iteration_index,
                    primitives=primitives,
                    settings=settings,
                    message_history=message_history,
                    suppress_tools_for_next_inference=suppress_tools_for_next_inference,
                    output_publication_mode=output_publication_mode,
                    run_inference=run_inference,
                )
                suppress_tools_for_next_inference = False
            outcome.record_inference(current_inference)
            if not current_inference.successful or current_inference.payload is None:
                failure_transition = await resolve_failed_inference_transition(
                    inference=current_inference,
                    message_history=message_history,
                    boundary_source_messages=boundary_source_messages,
                    relay_retry_attempted=relay_retry_attempted,
                    inference_admission_retries=inference_admission_retries,
                    max_inference_admission_retries=settings.inference_admission_max_retries,
                    logger=logger,
                    turn_cancelled=turn_cancelled,
                )
                if failure_transition.should_retry:
                    relay_retry_attempted = failure_transition.relay_retry_attempted
                    inference_admission_retries = failure_transition.inference_admission_retries
                    current_inference = None
                    continue
                if failure_transition.terminal_outcome is not None:
                    outcome.terminal_outcome = failure_transition.terminal_outcome
                outcome.final_text = failure_transition.final_text
                break
            relay_retry_attempted = False
            inference_admission_retries = 0
            if await turn_cancelled():
                outcome.terminal_outcome = build_cancelled_turn_terminal_outcome()
                break
            outcome.final_payload = dict(current_inference.payload)
            post_inference = await resolve_turn_loop_post_inference(
                final_payload=outcome.final_payload,
                assistant_text=current_inference.assistant_text,
                assistant_output_published=current_inference.assistant_output_published,
                current_inference_tool_calls=current_inference.tool_calls,
                current_inference_detected_tool_calls=current_inference.detected_tool_calls,
                current_inference_visible_text_chars=current_inference.visible_text_chars,
                current_inference_thinking_text_chars=current_inference.thinking_text_chars,
                finish_reason=current_inference.finish_reason,
                output_publication_mode=output_publication_mode,
                iteration_index=iteration_index,
                tool_sequence_state=tool_sequence_state,
                turn_state_writer=turn_state_writer,
                tool_context=tool_context,
                request_context=request_context,
                primitives=primitives,
                settings=settings,
                message_history=message_history,
                boundary_source_messages=boundary_source_messages,
                iteration_policy_state=iteration_policy_state,
                iteration_policy_config=iteration_policy_config,
                next_action_sequence=sequence_tracker.next_sequence,
                emit_event=emit_event,
                database_tool_calls=database_tool_calls,
                validate_visible_assistant_output=validate_visible_assistant_output,
                shape_cache=shape_cache,
            )
            assistant_text = post_inference.assistant_text
            tool_calls = post_inference.tool_calls
            if post_inference.assistant_output_published and assistant_text:
                outcome.final_text = assistant_text
            if await turn_cancelled():
                outcome.terminal_outcome = build_cancelled_turn_terminal_outcome()
                break
            decision = post_inference.decision
            iteration_policy_state = post_inference.next_policy_state
            if decision.control == PostInferenceControl.COMPLETE:
                break
            if decision.control == PostInferenceControl.TERMINATE:
                outcome.terminal_outcome = resolve_post_inference_terminal_outcome(decision)
                break
            if decision.control == PostInferenceControl.RETRY:
                suppress_tools_for_next_inference = decision.suppress_tools_for_next_iteration
                output_publication_mode = decision.next_output_publication_mode
                retry_transition = await advance_retry_after_compaction(
                    compact_messages=compact_messages,
                    iteration_index=iteration_index,
                    message_history=message_history,
                    boundary_source_messages=boundary_source_messages,
                    turn_cancelled=turn_cancelled,
                )
                if retry_transition.cancelled:
                    outcome.terminal_outcome = build_cancelled_turn_terminal_outcome()
                    break
                iteration_index = retry_transition.iteration_index
                message_history = retry_transition.message_history
                boundary_source_messages = retry_transition.boundary_source_messages
                current_inference = None
                continue
            if decision.control != PostInferenceControl.PROCEED_TOOLS:
                raise StateError(f"Unhandled post-inference control: {decision.control}")
            output_publication_mode = decision.next_output_publication_mode
        tool_transition = await advance_turn_loop_after_tools(
            phase_context=ToolPhaseExecutionContext(
                request_context=request_context,
                tool_context=tool_context,
                tool_call_processor=tool_call_processor,
                database_tool_calls=database_tool_calls,
                task_registry=task_registry,
                database_notifications=database_notifications,
                conversation_attention=conversation_attention,
                database_input_queue=database_input_queue,
                database_users=database_users,
                logger=logger,
                cancellation_history=cancellation_history,
                current_cancellation_id=current_cancellation_id,
                iteration_index=iteration_index,
                assistant_text=assistant_text,
                tool_calls=tool_calls,
                message_history=message_history,
                boundary_source_messages=boundary_source_messages,
                todo_state=todo_state,
                primitives=primitives,
                sequence_tracker=sequence_tracker,
                turn_state_writer=turn_state_writer,
                emit_event=emit_event,
                turn_cancelled=turn_cancelled,
                shape_cache=shape_cache,
            ),
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            settings=settings,
            compact_messages=compact_messages,
            final_payload=outcome.final_payload,
            total_tool_calls=total_tool_calls,
            output_publication_mode=output_publication_mode,
        )
        total_tool_calls = tool_transition.total_tool_calls
        if tool_transition.terminal_outcome is not None:
            outcome.terminal_outcome = tool_transition.terminal_outcome
        if tool_transition.completed:
            break
        iteration_index = tool_transition.iteration_index
        message_history = tool_transition.message_history
        boundary_source_messages = tool_transition.boundary_source_messages
        current_inference = None
        execute_tool_phase = False
        output_publication_mode = tool_transition.output_publication_mode
    return outcome.build_result(
        iteration_index=iteration_index,
        total_tool_calls=total_tool_calls,
    )
