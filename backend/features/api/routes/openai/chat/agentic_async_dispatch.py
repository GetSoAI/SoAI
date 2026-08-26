"""SoAI - Async accepted agentic chat dispatch [backend/features/api/routes/openai/chat/agentic_async_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import Response

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.request_source_resolution import resolve_request_source_for_request
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from features.agent.runtime.execution_preparation import (
    build_agent_turn_engine_dependencies,
)
from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
from features.agent.runtime.turn_lifecycle.claim import claim_agent_turn_for_execution
from features.agent.runtime.turn_todo_state import parse_agent_todo_state_payload
from features.api.routes.openai.chat.agentic_async_runner import (
    run_agentic_async_coordinator_task,
)
from features.api.routes.openai.chat.agentic_dispatch_support import (
    build_agentic_execution_inputs,
    prepare_agentic_async_accept_dispatch,
)
from features.api.routes.openai.chat.inference_request_failure_handling import (
    finalize_openai_running_turn_error_noncritical,
)
from features.api.runtime.responses import create_task_accepted_response
from features.api.runtime.task_metadata import build_inference_task_metadata

if TYPE_CHECKING:
    from core.events.types_models_requests import InferenceRequestReceived
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies

__all__ = ("maybe_execute_async_agentic_request",)

LOGGER_NAME = "SoAI.features.api.agentic_async_dispatch"
OPERATION = "api_openai.agentic_async.spawn"


async def maybe_execute_async_agentic_request(
    *,
    request: Request,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    request_json: JSONDict,
    tool_context: MCPToolContext | None,
    prepared_agent_request: PreparedExecutionRequest | None,
    request_event_class: type[InferenceRequestReceived],
    async_accept_requested: bool,
    is_streaming: bool,
    api_key_id: str | None,
    quota_reservation: JSONDict | None,
) -> Response | None:
    if (
        not async_accept_requested
        or is_streaming
        or tool_context is None
        or prepared_agent_request is None
    ):
        return None
    logger = get_logger(LOGGER_NAME)
    primitives, _turn_record = await claim_agent_turn_for_execution(
        deps=build_agent_turn_engine_dependencies(
            api_dependencies=api_context.dependencies,
            logger=logger,
        ),
        context=context,
        tool_context=tool_context,
        settings=prepared_agent_request.agent_settings,
        requested_model=prepared_agent_request.requested_model,
        todo_state=parse_agent_todo_state_payload(prepared_agent_request.todo_state),
        initial_active_inference_cancellation_id=None,
    )
    turn_cancellation_id = primitives.turn_cancellation_id
    timeout_value = await prepare_agentic_async_accept_dispatch(
        request,
        api_context,
        context,
        request_json,
        api_key_id,
        quota_reservation,
    )
    task_metadata = build_inference_task_metadata(
        context,
        request,
        prepared_agent_request.requested_model,
        "agentic_async_loop",
    )
    task_metadata["agent_turn_id"] = primitives.turn_id
    task_metadata["agentic"] = True
    coordinator_task = await create(
        api_context.dependencies.task_registry,
        TASK_TYPE_CHAT_COMPLETION,
        tool_context.user_id,
        tool_context.conv_id,
        "conversation",
        cancellation_id=turn_cancellation_id,
        status=TaskStatus.PENDING,
        status_message="Accepted",
        metadata=task_metadata,
        request_source=resolve_request_source_for_request(request),
        delivery_mode="async",
    )
    background_context = clone_request_context(
        context,
        task_id=coordinator_task.task_id,
        cancellation_id=turn_cancellation_id,
        agent_iteration_index=0,
    )
    execution_inputs = build_agentic_execution_inputs(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        context=background_context,
        tool_context=tool_context,
        prepared_agent_request=prepared_agent_request,
        request_event_class=request_event_class,
    )

    async def run_agentic_background_task() -> None:
        await run_agentic_async_coordinator_task(
            api_context=api_context,
            logger=logger,
            execution_inputs=execution_inputs,
            timeout_value=timeout_value,
            coordinator_task_id=coordinator_task.task_id,
        )

    try:
        background_task = spawn_tracked_task(
            run_agentic_background_task(),
            name="openai-agentic-async-coordinator",
            logger=logger,
            cancellation_binder=api_context.dependencies.task_cancellation_binder,
            cancellation_id=turn_cancellation_id,
            owner="api_openai.agentic_async",
            metadata={
                "conv_id": tool_context.conv_id,
                "task_id": coordinator_task.task_id,
                "turn_id": primitives.turn_id,
            },
            finalizer_tracker=api_context.dependencies.task_finalizer_tracker,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to spawn OpenAI agentic async turn.",
            operation=OPERATION,
        )
        is_recoverable = isinstance(exception, RECOVERABLE_EXCEPTIONS)
        finalize_error_type = str(coerced.code)
        if is_recoverable:
            cleanup_log_message = (
                "Failed to finalize agent turn after async agentic coordinator spawn failure "
                "(non-critical)."
            )
        else:
            cleanup_log_message = (
                "Failed to finalize agent turn after unexpected async agentic coordinator spawn "
                "failure (non-critical)."
            )
        await finalize_openai_running_turn_error_noncritical(
            api_context=api_context,
            logger=logger,
            context=context,
            tool_context=tool_context,
            error_message=coerced.message,
            error_type=finalize_error_type,
            operation="api_openai.agentic_async.spawn.turn_cleanup",
            log_message=cleanup_log_message,
        )
        await finalize(
            api_context.dependencies.task_registry,
            coordinator_task.task_id,
            TaskStatus.FAILED,
            error_code=coerced.http_status,
            error_message=coerced.message,
            status_message=coerced.message,
        )
        raise
    api_context.dependencies.application_control.track_background_task(background_task)
    response = create_task_accepted_response(
        task_id=coordinator_task.task_id,
        commit_deadline_ts_ms=None,
        operation_id=context.trace_id,
        preference_applied="respond-async",
    )
    return response
