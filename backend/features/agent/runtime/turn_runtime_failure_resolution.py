"""SoAI - Agent turn runtime failure resolution [backend/features/agent/runtime/turn_runtime_failure_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_ERROR
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exceptions import ConflictError, StateError
from features.agent.runtime.persisted_terminal_turn_replay import (
    resolve_persisted_terminal_turn_replay,
)
from features.agent.runtime.turn_iteration_policy_messages import get_cancelled_status
from features.agent.runtime.turn_lifecycle.finalize import finalize_running_turn_noncritical
from features.agent.runtime.turn_lifecycle.noncritical_finalization_request import (
    build_cancelled_turn_noncritical_finalization_request,
    build_error_turn_noncritical_finalization_request,
)

if TYPE_CHECKING:
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from features.agent.runtime.persisted_terminal_turn_replay import (
        PersistedTerminalTurnReplay,
    )
    from features.agent.runtime.turn_bootstrap import AgentTurnBootstrap
    from features.agent.runtime.turn_engine import AgentTurnEngineDependencies

__all__ = (
    "TurnRuntimeFailureResolution",
    "resolve_turn_cancellation_failure",
    "resolve_turn_runtime_exception_failure",
    "resolve_turn_write_conflict_failure",
)


@dataclass(frozen=True, slots=True)
class TurnRuntimeFailureResolution:
    final_status: str
    final_error_message: str | None
    final_error_type: str | None
    raised_error: BaseException | None
    persisted_terminal_turn_replay: PersistedTerminalTurnReplay | None = None


async def resolve_turn_write_conflict_failure(
    *,
    deps: AgentTurnEngineDependencies,
    bootstrap: AgentTurnBootstrap | None,
    exception: BaseException,
) -> TurnRuntimeFailureResolution:
    if bootstrap is None:
        raise StateError(
            "Agent turn write conflict occurred before bootstrap completed.",
        ) from exception
    replay = await resolve_persisted_terminal_turn_replay(
        database_agent_turns=deps.database_agent_turns,
        conv_id=bootstrap.primitives.conv_id,
        user_id=bootstrap.primitives.user_id,
        turn_id=bootstrap.primitives.turn_id,
    )
    if replay is None:
        raise ConflictError("Agent turn already finalized.") from exception
    return TurnRuntimeFailureResolution(
        final_status=replay.status,
        final_error_message=replay.error_message,
        final_error_type=replay.error_type,
        raised_error=None,
        persisted_terminal_turn_replay=replay,
    )


async def resolve_turn_cancellation_failure(
    *,
    deps: AgentTurnEngineDependencies,
    bootstrap: AgentTurnBootstrap | None,
    context: RequestContext,
    tool_context: MCPToolContext,
    operation: str,
    exception: asyncio.CancelledError,
) -> TurnRuntimeFailureResolution:
    if bootstrap is None:
        await uncancel_then_cleanup(
            finalize_running_turn_noncritical(
                database_agent_turns=deps.database_agent_turns,
                logger=deps.logger,
                request=build_cancelled_turn_noncritical_finalization_request(
                    trace_id=context.trace_id,
                    conv_id=tool_context.conv_id,
                    user_id=tool_context.user_id,
                    turn_id=context.agent_turn_id,
                    execution_token=context.agent_turn_execution_token,
                    operation=f"{operation}.bootstrap_cancelled",
                    log_message="Failed to finalize claimed agent turn after bootstrap cancellation (non-critical).",
                ),
            ),
        )
    final_status, final_error_message, final_error_type = get_cancelled_status()
    return TurnRuntimeFailureResolution(
        final_status=final_status,
        final_error_message=final_error_message,
        final_error_type=final_error_type,
        raised_error=exception,
    )


async def resolve_turn_runtime_exception_failure(
    *,
    deps: AgentTurnEngineDependencies,
    bootstrap: AgentTurnBootstrap | None,
    context: RequestContext,
    tool_context: MCPToolContext,
    operation: str,
    exception: BaseException,
) -> TurnRuntimeFailureResolution:
    raised_error = coerce_to_soai_error(exception, operation=operation)
    if bootstrap is None:
        await finalize_running_turn_noncritical(
            database_agent_turns=deps.database_agent_turns,
            logger=deps.logger,
            request=build_error_turn_noncritical_finalization_request(
                trace_id=context.trace_id,
                conv_id=tool_context.conv_id,
                user_id=tool_context.user_id,
                turn_id=context.agent_turn_id,
                execution_token=context.agent_turn_execution_token,
                error_message=raised_error.message,
                error_type=str(raised_error.code),
                operation=f"{operation}.bootstrap_error",
                log_message="Failed to finalize claimed agent turn after bootstrap error (non-critical).",
            ),
        )
    return TurnRuntimeFailureResolution(
        final_status=AGENT_TURN_STATUS_ERROR,
        final_error_message=raised_error.message,
        final_error_type=str(raised_error.code),
        raised_error=raised_error,
    )
