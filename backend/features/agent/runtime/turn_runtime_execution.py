"""SoAI - Shared agent turn runtime execution [backend/features/agent/runtime/turn_runtime_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_COMPLETED,
)
from core.agent.turn_write_conflicts import AgentTurnAlreadyFinalizedDuringWriteError
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.runtime.request_context import RequestContext
from features.agent.runtime.turn_bootstrap_initialization import initialize_agent_turn
from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
)
from features.agent.runtime.turn_loop import execute_turn_loop
from features.agent.runtime.turn_loop_models import TurnLoopInferenceResult
from features.agent.runtime.turn_runtime_compaction import (
    build_runtime_compaction_callback,
)
from features.agent.runtime.turn_runtime_completion import (
    finalize_and_build_turn_runtime_execution,
)
from features.agent.runtime.turn_runtime_execution_models import TurnRuntimeExecution
from features.agent.runtime.turn_runtime_failure_resolution import (
    TurnRuntimeFailureResolution,
    resolve_turn_cancellation_failure,
    resolve_turn_runtime_exception_failure,
    resolve_turn_write_conflict_failure,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.openai.token_accounting import PromptOccupancy
    from core.openai.usage.models import CanonicalUsage
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.activity_result import (
        PreparedAutoCompactionSnapshot,
    )
    from features.agent.runtime.persisted_terminal_turn_replay import (
        PersistedTerminalTurnReplay,
    )
    from features.agent.runtime.tool_sequence_reservations import (
        ToolSequenceIndexReservation,
    )
    from features.agent.runtime.turn_bootstrap import AgentTurnBootstrap
    from features.agent.runtime.turn_engine import (
        AgentTurnEngineDependencies,
    )
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = (
    "TurnRuntimeExecution",
    "execute_agent_turn_runtime",
)


async def execute_agent_turn_runtime(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    initial_messages: list[JSONDict],
    initial_boundary_source_messages: list[JSONDict],
    base_request_payload: JSONDict,
    settings: AgentSettings,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    run_inference: Callable[
        [
            int,
            str,
            list[JSONDict],
            bool,
            AgentOutputPublicationMode,
            AgentTurnBootstrap,
        ],
        Awaitable[TurnLoopInferenceResult],
    ],
    prepared_auto_compaction: PreparedAutoCompactionSnapshot | None,
    turn_id: str | None,
    initial_active_inference_cancellation_id: str | None,
    operation: str,
    include_usage_in_result: bool,
    on_tool_sequence_indexes_reserved: Callable[[ToolSequenceIndexReservation], None] | None = None,
    on_pre_compaction_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
    on_compacted_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
    validate_visible_assistant_output: (
        Callable[
            [str],
            Awaitable[PreviewContractOutputValidationResult],
        ]
        | None
    ) = None,
    initial_output_publication_mode: AgentOutputPublicationMode = (
        AgentOutputPublicationMode.STREAM_LIVE
    ),
) -> TurnRuntimeExecution:
    bootstrap: AgentTurnBootstrap | None = None
    message_history = list(initial_messages)
    boundary_source_messages = [dict(message) for message in initial_boundary_source_messages]
    usage_aggregate: CanonicalUsage | None = None
    final_status = AGENT_TURN_STATUS_COMPLETED
    final_error_message: str | None = None
    final_error_type: str | None = None
    raised_error: BaseException | None = None
    loop_result = None
    persisted_terminal_turn_replay: PersistedTerminalTurnReplay | None = None
    failure_resolution: TurnRuntimeFailureResolution | None = None
    try:
        bootstrap = await initialize_agent_turn(
            deps=deps,
            context=context,
            tool_context=tool_context,
            settings=settings,
            base_request_payload=base_request_payload,
            turn_id=turn_id,
            initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
        )
        message_history = await bootstrap.compact_initial_messages(
            message_history=message_history,
            boundary_source_messages=boundary_source_messages,
            base_request_payload=base_request_payload,
            summarize_messages=summarize_messages,
            prepared_auto_compaction=prepared_auto_compaction,
            on_tool_sequence_indexes_reserved=on_tool_sequence_indexes_reserved,
            on_pre_compaction_prompt_occupancy=on_pre_compaction_prompt_occupancy,
            on_compacted_prompt_occupancy=on_compacted_prompt_occupancy,
        )
        boundary_source_messages = [dict(message) for message in message_history]
        compact_messages = build_runtime_compaction_callback(
            deps=deps,
            bootstrap=bootstrap,
            base_request_payload=base_request_payload,
            settings=settings,
            summarize_messages=summarize_messages,
            on_tool_sequence_indexes_reserved=on_tool_sequence_indexes_reserved,
            on_pre_compaction_prompt_occupancy=on_pre_compaction_prompt_occupancy,
            on_compacted_prompt_occupancy=on_compacted_prompt_occupancy,
        )

        async def run_bootstrapped_inference(
            iteration_index: int,
            cancellation_id: str,
            current_history: list[JSONDict],
            suppress_tools: bool,
            output_publication_mode: AgentOutputPublicationMode,
        ) -> TurnLoopInferenceResult:
            return await run_inference(
                iteration_index,
                cancellation_id,
                current_history,
                suppress_tools,
                output_publication_mode,
                bootstrap,
            )

        loop_result = await execute_turn_loop(
            request_context=context,
            tool_context=tool_context,
            tool_call_processor=deps.tool_call_processor,
            database_tool_calls=deps.database_tool_calls,
            task_registry=deps.task_registry,
            database_notifications=deps.database_notifications,
            conversation_attention=deps.conversation_attention,
            database_input_queue=deps.database_input_queue,
            database_users=deps.database_users,
            logger=deps.logger,
            cancellation_history=deps.cancellation_history,
            prompt_token_counter=deps.prompt_token_counter,
            base_request_payload=base_request_payload,
            settings=settings,
            message_history=message_history,
            boundary_source_messages=boundary_source_messages,
            todo_state=bootstrap.todo_state,
            primitives=bootstrap.primitives,
            sequence_tracker=bootstrap.sequence_tracker,
            tool_sequence_state=bootstrap.tool_sequence_state,
            turn_state_writer=bootstrap.turn_state_writer,
            emit_event=bootstrap.emit_event,
            turn_cancelled=bootstrap.turn_cancelled,
            iteration_policy_state=bootstrap.iteration_policy_state,
            iteration_policy_config=bootstrap.iteration_policy_config,
            compact_messages=compact_messages,
            run_inference=run_bootstrapped_inference,
            validate_visible_assistant_output=validate_visible_assistant_output,
            initial_output_publication_mode=initial_output_publication_mode,
        )
        usage_aggregate = loop_result.usage_aggregate
        final_status = loop_result.final_status
        final_error_message = loop_result.final_error_message
        final_error_type = loop_result.final_error_type
    except AgentTurnAlreadyFinalizedDuringWriteError as exception:
        failure_resolution = await resolve_turn_write_conflict_failure(
            deps=deps,
            bootstrap=bootstrap,
            exception=exception,
        )
    except asyncio.CancelledError as exception:
        failure_resolution = await resolve_turn_cancellation_failure(
            deps=deps,
            bootstrap=bootstrap,
            context=context,
            tool_context=tool_context,
            operation=operation,
            exception=exception,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failure_resolution = await resolve_turn_runtime_exception_failure(
            deps=deps,
            bootstrap=bootstrap,
            context=context,
            tool_context=tool_context,
            operation=operation,
            exception=exception,
        )
    if failure_resolution is not None:
        final_status = failure_resolution.final_status
        final_error_message = failure_resolution.final_error_message
        final_error_type = failure_resolution.final_error_type
        raised_error = failure_resolution.raised_error
        persisted_terminal_turn_replay = failure_resolution.persisted_terminal_turn_replay
    if bootstrap is None:
        if raised_error is not None:
            raise raised_error
        raise StateError("Agent turn runtime failed before bootstrap completed.")
    return await finalize_and_build_turn_runtime_execution(
        deps=deps,
        context=context,
        bootstrap=bootstrap,
        loop_result=loop_result,
        usage_aggregate=usage_aggregate,
        final_status=final_status,
        final_error_message=final_error_message,
        final_error_type=final_error_type,
        raised_error=raised_error,
        include_usage_in_result=include_usage_in_result,
        persisted_terminal_turn_replay=persisted_terminal_turn_replay,
    )
