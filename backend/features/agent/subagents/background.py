"""SoAI - Subagent background execution [backend/features/agent/subagents/background.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_COMPLETED,
    AGENT_TURN_STATUS_ERROR,
    AGENT_TURN_STATUS_MAX_ITERATIONS,
)
from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.execution.owned_execution_tasks import (
    finalize_owned_execution_task,
    mark_owned_execution_running,
)
from core.runtime.request_context import RequestContext
from features.agent.runtime.turn_lifecycle.finalize import (
    finalize_running_turn_noncritical,
)
from features.agent.runtime.turn_lifecycle.noncritical_finalization_request import (
    build_cancelled_turn_noncritical_finalization_request,
    build_error_turn_noncritical_finalization_request,
)
from features.agent.subagents.background_finalization import (
    finalize_subagent_background_execution,
)
from features.agent.subagents.background_parent_stream_setup import (
    maybe_build_parent_update_bridge,
    maybe_subscribe_tool_event_forwarder,
    prime_parent_update_bridge_noncritical,
)
from features.agent.subagents.background_running_persistence import (
    SubagentRunningTurnPersistence,
)
from features.agent.subagents.background_runtime_state import (
    SubagentBackgroundRuntimeState,
)
from features.agent.subagents.coordinator.cancellation import (
    cancel_subagent_active_inference_scope_noncritical,
)
from features.agent.subagents.stream_execution import execute_subagent_stream

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "SubagentBackgroundExecutor",
    "SubagentBackgroundExecutorDependencies",
)

OPERATION_SUBAGENT_BACKGROUND_EXECUTE = "agent.subagents.background.execute"
OPERATION_SUBAGENT_BACKGROUND_EXECUTE_CANCELLED = "agent.subagents.background.execute.cancelled"
OPERATION_SUBAGENT_BACKGROUND_EXECUTE_ERROR = "agent.subagents.background.execute.error"
OPERATION_SUBAGENT_BACKGROUND_CANCEL_ACTIVE_INFERENCE_SCOPE = (
    "agent.subagents.background.cancel_active_inference_scope"
)


@dataclass(frozen=True, slots=True)
class SubagentBackgroundExecutorDependencies:
    api_dependencies: ApiDependencies
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SubagentBackgroundExecutorDependencies",
            api_dependencies=self.api_dependencies,
            logger=self.logger,
        )


async def _finalize_subagent_turn_cancelled(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    subagent_context: RequestContext,
    subagent_tool_context: MCPToolContext,
) -> None:
    await uncancel_then_cleanup(
        finalize_running_turn_noncritical(
            database_agent_turns=api_dependencies.database_agent_turns,
            logger=logger,
            request=build_cancelled_turn_noncritical_finalization_request(
                trace_id=subagent_context.trace_id,
                conv_id=subagent_tool_context.conv_id,
                user_id=subagent_tool_context.user_id,
                turn_id=subagent_context.agent_turn_id,
                execution_token=subagent_context.agent_turn_execution_token,
                operation=OPERATION_SUBAGENT_BACKGROUND_EXECUTE_CANCELLED,
                log_message="Failed to finalize subagent turn after cancellation (non-critical).",
            ),
        ),
    )


@dataclass(slots=True)
class SubagentBackgroundExecutor:
    _api_dependencies: ApiDependencies
    _logger: LoggerProtocol

    def __init__(self, deps: SubagentBackgroundExecutorDependencies) -> None:
        self._api_dependencies = deps.api_dependencies
        self._logger = deps.logger

    async def execute(
        self,
        *,
        subagent_context: RequestContext,
        subagent_tool_context: MCPToolContext,
        requested_model: str,
        settings: AgentSettings,
        execution_request: JSONDict,
        coordinator_task_id: str,
        task_text: str,
        task_context: str | None,
    ) -> None:
        runtime_state = SubagentBackgroundRuntimeState(
            api_dependencies=self._api_dependencies,
            logger=self._logger,
            subagent_context=subagent_context,
            subagent_tool_context=subagent_tool_context,
            requested_model=requested_model,
            token_estimation_profile=settings.token_estimation_profile,
            running_persistence=SubagentRunningTurnPersistence(
                api_dependencies=self._api_dependencies,
                logger=self._logger,
                subagent_context=subagent_context,
                subagent_tool_context=subagent_tool_context,
            ),
        )
        tool_event_forwarder = None
        final_owned_status: str | None = None
        final_owned_status_message: str | None = None
        final_owned_error_message: str | None = None
        try:
            runtime_state.parent_tool_call_update_bridge = maybe_build_parent_update_bridge(
                api_dependencies=self._api_dependencies,
                logger=self._logger,
                subagent_context=subagent_context,
                subagent_tool_context=subagent_tool_context,
            )
            await prime_parent_update_bridge_noncritical(
                api_dependencies=self._api_dependencies,
                logger=self._logger,
                subagent_context=subagent_context,
                subagent_tool_context=subagent_tool_context,
                bridge=runtime_state.parent_tool_call_update_bridge,
            )
            tool_event_forwarder = maybe_subscribe_tool_event_forwarder(
                api_dependencies=self._api_dependencies,
                subagent_context=subagent_context,
                subagent_tool_context=subagent_tool_context,
                bridge=runtime_state.parent_tool_call_update_bridge,
            )
            await mark_owned_execution_running(
                self._api_dependencies.task_registry,
                owner_task_id=coordinator_task_id,
                status_message="Running subagent.",
            )
            execution = await execute_subagent_stream(
                api_dependencies=self._api_dependencies,
                logger=self._logger,
                subagent_context=subagent_context,
                subagent_tool_context=subagent_tool_context,
                requested_model=requested_model,
                settings=settings,
                execution_request=execution_request,
                task_text=task_text,
                task_context=task_context,
                on_stream_initialized=runtime_state.handle_stream_initialized,
                on_visible_deltas=runtime_state.handle_preview_deltas,
                on_raw_bytes=runtime_state.handle_raw_bytes,
            )
            runtime_state.prompt_tokens = execution.prompt_tokens
            runtime_state.prompt_tokens_capped = execution.prompt_tokens_capped
            runtime_state.prompt_tokens_capped_reason = execution.prompt_tokens_capped_reason
            runtime_state.prompt_tokens_precision = execution.prompt_tokens_precision
            runtime_state.final_token_usage = execution.final_token_usage
            final_owned_status = (
                AGENT_TURN_STATUS_MAX_ITERATIONS
                if execution.reached_max_iterations
                else AGENT_TURN_STATUS_COMPLETED
            )
            final_owned_status_message = (
                "Max iterations reached" if execution.reached_max_iterations else "Completed"
            )
        except TaskCancelledError as exception:
            final_owned_status = AGENT_TURN_STATUS_CANCELLED
            final_owned_error_message = str(exception.reason or "Cancelled")
            final_owned_status_message = "Cancelled"
            await _finalize_subagent_turn_cancelled(
                api_dependencies=self._api_dependencies,
                logger=self._logger,
                subagent_context=subagent_context,
                subagent_tool_context=subagent_tool_context,
            )
            raise
        except asyncio.CancelledError:
            final_owned_status = AGENT_TURN_STATUS_CANCELLED
            final_owned_error_message = "Cancelled by parent agent."
            final_owned_status_message = "Cancelled"
            await _finalize_subagent_turn_cancelled(
                api_dependencies=self._api_dependencies,
                logger=self._logger,
                subagent_context=subagent_context,
                subagent_tool_context=subagent_tool_context,
            )
            raise
        except Exception as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_SUBAGENT_BACKGROUND_EXECUTE,
            )
            log_exception(
                self._logger,
                coerced,
                message="Subagent background execution failed.",
                trace_id=subagent_context.trace_id,
                operation=OPERATION_SUBAGENT_BACKGROUND_EXECUTE,
                details={
                    "conv_id": subagent_tool_context.conv_id,
                    "turn_id": subagent_context.agent_turn_id,
                    "owner_task_id": coordinator_task_id,
                },
            )
            final_owned_status = AGENT_TURN_STATUS_ERROR
            final_owned_error_message = str(coerced)
            final_owned_status_message = "Failed"
            await cancel_subagent_active_inference_scope_noncritical(
                api_dependencies=self._api_dependencies,
                logger=self._logger,
                trace_id=subagent_context.trace_id,
                conv_id=subagent_tool_context.conv_id,
                user_id=subagent_tool_context.user_id,
                subagent_id=str(subagent_context.agent_turn_id or ""),
                reason="Subagent background failed.",
                operation=OPERATION_SUBAGENT_BACKGROUND_CANCEL_ACTIVE_INFERENCE_SCOPE,
                log_message="Failed to cancel active subagent inference scope (non-critical).",
            )
            await uncancel_then_cleanup(
                finalize_running_turn_noncritical(
                    database_agent_turns=self._api_dependencies.database_agent_turns,
                    logger=self._logger,
                    request=build_error_turn_noncritical_finalization_request(
                        trace_id=subagent_context.trace_id,
                        conv_id=subagent_tool_context.conv_id,
                        user_id=subagent_tool_context.user_id,
                        turn_id=subagent_context.agent_turn_id,
                        execution_token=subagent_context.agent_turn_execution_token,
                        error_message=str(coerced),
                        error_type=AGENT_TURN_STATUS_ERROR,
                        operation=OPERATION_SUBAGENT_BACKGROUND_EXECUTE_ERROR,
                        log_message=(
                            "Failed to finalize subagent turn after background error "
                            "(non-critical)."
                        ),
                    ),
                ),
            )
            raise
        finally:
            if tool_event_forwarder is not None:
                tool_event_forwarder.unsubscribe()
            await uncancel_then_cleanup(
                finalize_subagent_background_execution(
                    api_dependencies=self._api_dependencies,
                    logger=self._logger,
                    subagent_context=subagent_context,
                    subagent_tool_context=subagent_tool_context,
                    runtime_state=runtime_state,
                ),
            )
            if final_owned_status is not None and final_owned_status_message is not None:
                await uncancel_then_cleanup(
                    finalize_owned_execution_task(
                        self._api_dependencies.task_registry,
                        owner_task_id=coordinator_task_id,
                        final_status=final_owned_status,
                        error_message=final_owned_error_message,
                        status_message=final_owned_status_message,
                    ),
                )
