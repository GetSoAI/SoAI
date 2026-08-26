"""SoAI - Agent turn runtime completion and finalization [backend/features/agent/runtime/turn_runtime_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.agent.turn_write_conflicts import AgentTurnAlreadyFinalizedDuringWriteError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ConflictError
from core.openai.usage.serialization import build_internal_usage_payload
from core.runtime.request_context import RequestContext
from features.agent.runtime.persisted_terminal_turn_replay import (
    PersistedTerminalTurnReplay,
    resolve_persisted_terminal_turn_replay,
)
from features.agent.runtime.turn_finalization import (
    build_agent_turn_result,
    cancel_active_subagent_turns,
    finalize_turn_state,
)
from features.agent.runtime.turn_runtime_execution_models import TurnRuntimeExecution
from features.agent.runtime.turn_terminal_state import resolve_turn_terminal_snapshot

if TYPE_CHECKING:
    from core.openai.usage.models import CanonicalUsage
    from features.agent.runtime.turn_bootstrap import AgentTurnBootstrap
    from features.agent.runtime.turn_engine import (
        AgentTurnEngineDependencies,
        AgentTurnResult,
    )
    from features.agent.runtime.turn_loop_models import TurnLoopResult

__all__ = ("finalize_and_build_turn_runtime_execution",)


async def finalize_and_build_turn_runtime_execution(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    bootstrap: AgentTurnBootstrap,
    loop_result: TurnLoopResult | None,
    usage_aggregate: CanonicalUsage | None,
    final_status: str,
    final_error_message: str | None,
    final_error_type: str | None,
    raised_error: BaseException | None,
    include_usage_in_result: bool,
    persisted_terminal_turn_replay: PersistedTerminalTurnReplay | None = None,
) -> TurnRuntimeExecution:
    should_preserve_active_subagents = False
    if loop_result is not None:
        should_preserve_active_subagents = loop_result.terminal_outcome.preserve_active_subagents
    if context.agent_turn_scope != TURN_SCOPE_SUBAGENT and not should_preserve_active_subagents:
        subagent_cleanup = cancel_active_subagent_turns(
            database_agent_turns=deps.database_agent_turns,
            task_registry=deps.task_registry,
            conv_id=bootstrap.primitives.conv_id,
            user_id=bootstrap.primitives.user_id,
            parent_turn_id=bootstrap.primitives.turn_id,
        )
        if isinstance(raised_error, asyncio.CancelledError):
            await uncancel_then_cleanup(subagent_cleanup)
        else:
            await subagent_cleanup
    loop_terminal_snapshot = loop_result.terminal_snapshot if loop_result is not None else None
    resolved_terminal_turn_replay = persisted_terminal_turn_replay
    if resolved_terminal_turn_replay is None:
        terminal_snapshot = resolve_turn_terminal_snapshot(
            loop_terminal_snapshot=loop_terminal_snapshot,
            turn_state_writer=bootstrap.turn_state_writer,
            persisted_terminal_turn_replay=None,
        )
        finalization = finalize_turn_state(
            turn_state_writer=bootstrap.turn_state_writer,
            emit_event=bootstrap.emit_event,
            sequence_tracker=bootstrap.sequence_tracker,
            primitives=bootstrap.primitives,
            iteration_index=terminal_snapshot.iteration_index,
            final_status=final_status,
            final_text=terminal_snapshot.assistant_text,
            reached_max_iterations=terminal_snapshot.reached_max_iterations,
            final_error_message=final_error_message,
            final_error_type=final_error_type,
            token_usage=(
                build_internal_usage_payload(usage_aggregate)
                if usage_aggregate is not None
                else None
            ),
        )
        try:
            if isinstance(raised_error, asyncio.CancelledError):
                await uncancel_then_cleanup(finalization)
            else:
                await finalization
        except AgentTurnAlreadyFinalizedDuringWriteError as exception:
            resolved_terminal_turn_replay = await resolve_persisted_terminal_turn_replay(
                database_agent_turns=deps.database_agent_turns,
                conv_id=bootstrap.primitives.conv_id,
                user_id=bootstrap.primitives.user_id,
                turn_id=bootstrap.primitives.turn_id,
            )
            if resolved_terminal_turn_replay is None:
                raise ConflictError("Agent turn already finalized.") from exception
    terminal_snapshot = resolve_turn_terminal_snapshot(
        loop_terminal_snapshot=loop_terminal_snapshot,
        turn_state_writer=bootstrap.turn_state_writer,
        persisted_terminal_turn_replay=resolved_terminal_turn_replay,
    )
    result: AgentTurnResult = build_agent_turn_result(
        final_payload=loop_result.final_payload if loop_result is not None else {},
        usage_aggregate=usage_aggregate if include_usage_in_result else None,
        reached_max_iterations=terminal_snapshot.reached_max_iterations,
    )
    if raised_error is not None:
        raise raised_error
    return TurnRuntimeExecution(
        result=result,
        usage_aggregate=usage_aggregate,
        stream_id=loop_result.stream_id if loop_result is not None else None,
        persisted_terminal_turn_replay=resolved_terminal_turn_replay,
    )
