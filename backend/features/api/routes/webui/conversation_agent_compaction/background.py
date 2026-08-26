"""SoAI - Manual compaction background task startup [backend/features/api/routes/webui/conversation_agent_compaction/background.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from starlette.requests import Request

from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.agent.turn_snapshot import require_agent_turn_snapshot
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.logging.protocols import LoggerProtocol
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.agent.runtime.turn_lifecycle.finalize import (
    finalize_running_turn_noncritical,
)
from features.agent.runtime.turn_lifecycle.noncritical_finalization_request import (
    build_error_turn_noncritical_finalization_request,
)
from features.api.routes.webui.conversation_agent_compaction.context import (
    resolve_summarizer_budget,
)
from features.api.routes.webui.conversation_agent_compaction.execution_identity import (
    ManualCompactionExecutionIdentity,
)
from features.api.routes.webui.conversation_agent_compaction.message_persistence import (
    persist_manual_compaction_terminal_message,
)
from features.api.routes.webui.conversation_agent_compaction.runner import (
    run_manual_compaction,
)
from features.api.routes.webui.conversation_agent_compaction.start_events import (
    publish_manual_compaction_start_events,
)
from features.api.routes.webui.conversation_agent_compaction.start_state_claims import (
    ManualCompactionStartState,
)
from features.api.routes.webui.conversation_agent_compaction.terminal_state import (
    build_manual_compaction_terminal_outcome,
)
from features.api.routes.webui.conversation_agent_compaction.turn_state import (
    publish_manual_compaction_failure,
)
from features.api.runtime.agent_state_payloads import build_agent_checkpoint_payload
from features.api.runtime.context import ApiContext
from features.api.runtime.current_user import CurrentUser
from features.api.runtime.errors import raise_server_error
from features.api.streaming.stream_dependencies import build_stream_dependencies

if TYPE_CHECKING:
    from core.database.requests import ManualCompactionStartCommitResult

__all__ = ("start_manual_compaction_background_task",)

OPERATION_WEBUI_AGENT_COMPACT_START = "webui.agent_compaction.start"
START_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    AttributeError,
    KeyError,
    TypeError,
    ValueError,
)


async def _build_manual_compaction_start_checkpoint_payload(
    *,
    api_context: ApiContext,
    start_state: ManualCompactionStartState,
    user_id: int,
) -> JSONDict:
    turn_record = await api_context.dependencies.database_agent_turns.get_turn(
        conv_id=start_state.conv_id,
        user_id=user_id,
        turn_id=start_state.turn_id,
    )
    if turn_record is None:
        raise SoAIError("Manual compaction start turn state is missing after persistence.")
    turn_snapshot = require_agent_turn_snapshot(turn_record)
    return build_agent_checkpoint_payload(
        snapshot=turn_snapshot,
        subagent_snapshots=[],
    )


async def start_manual_compaction_background_task(
    request: Request,
    api_context: ApiContext,
    current_user: CurrentUser,
    start_state: ManualCompactionStartState,
    logger: LoggerProtocol,
) -> JSONDict:
    try:
        base_context = request.state.context
    except AttributeError as exception:
        raise SoAIError(
            "Manual compaction RequestContext is missing from request state.",
        ) from exception
    if not isinstance(base_context, RequestContext):
        raise SoAIError("Manual compaction RequestContext is invalid.")
    background_context: RequestContext | None = None
    background_cancellation_id = start_state.turn_cancellation_id
    background_task: asyncio.Task[None] | None = None
    start_result: ManualCompactionStartCommitResult | None = None
    try:
        start_result = await publish_manual_compaction_start_events(
            api_context=api_context,
            current_user=current_user,
            start_state=start_state,
            logger=logger,
        )
        start_checkpoint_payload = await _build_manual_compaction_start_checkpoint_payload(
            api_context=api_context,
            start_state=start_state,
            user_id=current_user["id"],
        )

        background_context = clone_request_context(
            base_context,
            cancellation_id=start_state.turn_cancellation_id,
            agent_mode=start_state.mode,
            agent_turn_id=start_state.turn_id,
            agent_turn_scope=TURN_SCOPE_ROOT,
            agent_turn_execution_token=start_state.execution_token,
            agent_iteration_index=start_state.iteration_index,
        )
        if not isinstance(background_context, RequestContext):
            raise SoAIError("Manual compaction request context clone is invalid.")

        stream_dependencies = build_stream_dependencies(api_context.dependencies)
        committed_start_result = start_result

        async def run_compaction_background() -> None:
            await run_manual_compaction(
                request=request,
                api_context=api_context,
                stream_dependencies=stream_dependencies,
                context=background_context,
                conv_id=start_state.conv_id,
                user_id=current_user["id"],
                turn_id=start_state.turn_id,
                iteration_index=start_state.iteration_index,
                tool_call_id=start_state.tool_call_id,
                tool_started_at_ms=int(committed_start_result.assistant_at_ms),
                model=start_state.model,
                context_window_tokens=start_state.context_window_tokens,
                compaction_limit=start_state.compaction_limit,
                summarizer_budget=resolve_summarizer_budget(
                    config=api_context.dependencies.config,
                    context_window_tokens=start_state.context_window_tokens,
                ),
                replace_assistant_at_ms=start_state.replace_assistant_at_ms,
                replace_tool_call_id=start_state.replace_tool_call_id,
            )

        background_task = spawn_tracked_task(
            run_compaction_background(),
            name=f"webui-agent-compaction-{start_state.turn_id}",
            logger=logger,
            cancellation_binder=api_context.dependencies.task_cancellation_binder,
            cancellation_id=background_cancellation_id,
            owner="webui.agent.compact",
            finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
        )
        api_context.dependencies.application_control.track_background_task(background_task)
        return start_checkpoint_payload
    except START_FAILURE_EXCEPTIONS as exception:
        if background_task is not None and not background_task.done():
            background_task.cancel()
        trace_id = (
            background_context.trace_id if background_context is not None else base_context.trace_id
        )
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_WEBUI_AGENT_COMPACT_START,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to start manual compaction task.",
            operation=OPERATION_WEBUI_AGENT_COMPACT_START,
            level="error",
        )
        completed_at_ms = int(epoch_ms())
        if start_result is None:
            raise_server_error(request, coerced.message)
        terminal_outcome = build_manual_compaction_terminal_outcome(
            status="error",
            result_text="Context compaction failed.",
            prompt_message=None,
            error_message=coerced.message,
            result_details=None,
        )
        persisted_message = await persist_manual_compaction_terminal_message(
            api_context=api_context,
            conv_id=start_state.conv_id,
            user_id=current_user["id"],
            model_id=start_state.model,
            assistant_at_ms=int(start_result.assistant_at_ms),
            compaction_turn_id=start_state.turn_id,
            compaction_iteration_index=start_state.iteration_index,
            compaction_tool_call_id=start_state.tool_call_id,
            compaction_started_at_ms=int(start_result.assistant_at_ms),
            compaction_completed_at_ms=completed_at_ms,
            compaction_terminal_outcome=terminal_outcome,
            execution_token=start_state.execution_token,
            turn_cancellation_id=start_state.turn_cancellation_id,
            error_type=str(coerced.code),
            replace_assistant_at_ms=start_state.replace_assistant_at_ms,
            replace_tool_call_id=start_state.replace_tool_call_id,
        )
        message_index = int(persisted_message.message_index)
        try:
            execution_identity = ManualCompactionExecutionIdentity(
                conv_id=start_state.conv_id,
                user_id=current_user["id"],
                turn_id=start_state.turn_id,
                iteration_index=start_state.iteration_index,
                tool_call_id=start_state.tool_call_id,
                tool_started_at_ms=int(start_result.assistant_at_ms),
            )
            await publish_manual_compaction_failure(
                api_context=api_context,
                logger=logger,
                identity=execution_identity,
                message_index=message_index,
                completed_at_ms=completed_at_ms,
                tool_completion_sequence=int(persisted_message.tool_completion_sequence),
                turn_terminal_sequence=int(persisted_message.turn_terminal_sequence),
                error_message=coerced.message,
                error_type=str(coerced.code),
                terminal_outcome=terminal_outcome,
            )
        except START_FAILURE_EXCEPTIONS as publish_exception:
            publish_coerced = coerce_to_soai_error(
                publish_exception,
                operation="webui.agent.compact.start.failure_publish",
            )
            log_exception(
                logger,
                publish_coerced,
                message="Failed to publish manual compaction start failure state.",
                operation=OPERATION_WEBUI_AGENT_COMPACT_START,
                level="warning",
            )
            await finalize_running_turn_noncritical(
                database_agent_turns=api_context.dependencies.database_agent_turns,
                logger=logger,
                request=build_error_turn_noncritical_finalization_request(
                    trace_id=str(trace_id),
                    conv_id=start_state.conv_id,
                    user_id=current_user["id"],
                    turn_id=start_state.turn_id,
                    execution_token=start_state.execution_token,
                    error_message=coerced.message,
                    error_type=str(coerced.code),
                    operation="webui.agent.compact.start.turn_cleanup",
                    log_message=(
                        "Failed to finalize manual compaction turn after background "
                        "start failure (non-critical)."
                    ),
                ),
            )
        if isinstance(exception, SoAIError):
            raise
        raise_server_error(request, "Failed to start manual compaction.")
