"""SoAI - Chat stream start execution flow [backend/features/api/routes/system/events/chat_stream/start_command_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError, Task
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from features.api.routes.system.events.chat_stream.start_failure_finalization import (
    ChatStreamStartFailureBoundary,
    build_chat_stream_start_failure_context,
    finalize_chat_stream_start_failure,
)
from features.api.routes.system.events.chat_stream.start_pipeline_registration import (
    ChatStreamStartPipelineFailure,
    register_ws_chat_stream_runtime_or_error,
)
from features.api.routes.system.events.chat_stream.start_preparation_execution import (
    prepare_registered_ws_chat_stream_runtime,
)
from features.api.routes.system.events.chat_stream.start_preparation_finalization import (
    finalize_preparation_cancelled,
)
from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    from core.conversations.assistant_turn_variant_identity import (
        AssistantTurnVariantIdentity,
    )
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.request_message_source import (
        AgenticRequestMessageSource,
    )

__all__ = ("start_chat_stream_runtime",)


async def start_chat_stream_runtime(
    *,
    failure_boundary: ChatStreamStartFailureBoundary,
    chat_streams: dict[str, AssistantTimelineRuntime],
    request_json: JSONDict,
    identity: AssistantTurnVariantIdentity,
    message_count: int,
    canonical_history: list[JSONDict],
    extra_system_messages: tuple[str, ...],
    trace_id: str | None,
    logger: LoggerProtocol,
    agentic_message_source: AgenticRequestMessageSource | None = None,
) -> None:
    runtime = await register_ws_chat_stream_runtime_or_error(
        request=failure_boundary.request,
        api_context=failure_boundary.api_context,
        conv_id=failure_boundary.conv_id,
        request_id=failure_boundary.request_id,
        user_id=failure_boundary.user_id,
        model_id=failure_boundary.model_id,
        identity=identity,
        message_index=message_count,
        quota_key_id=None,
        quota_token_reservation=None,
        trace_id=trace_id,
        logger=logger,
    )
    if isinstance(runtime, ChatStreamStartPipelineFailure):
        failure_context = build_chat_stream_start_failure_context(
            boundary=failure_boundary,
            identity=identity,
            message_index=message_count,
        )
        await finalize_chat_stream_start_failure(
            context=failure_context,
            error_code=runtime.error_code,
            error_message=runtime.error_message,
        )
        return
    execution_started = False
    preparation_entered = False

    async def execute_owned_preparation() -> None:
        nonlocal execution_started, preparation_entered
        execution_started = True
        try:
            async with (
                failure_boundary.api_context.dependencies.conversation_agent_settings_locks.lock(
                    (failure_boundary.user_id, failure_boundary.conv_id),
                )
            ):
                preparation_entered = True
                await prepare_registered_ws_chat_stream_runtime(
                    request=failure_boundary.request,
                    api_context=failure_boundary.api_context,
                    stream_dependencies=failure_boundary.stream_dependencies,
                    chat_streams=chat_streams,
                    runtime=runtime,
                    request_json=request_json,
                    identity=identity,
                    message_count=message_count,
                    canonical_history=canonical_history,
                    extra_system_messages=extra_system_messages,
                    agentic_message_source=agentic_message_source,
                    trace_id=trace_id,
                    logger=logger,
                )
        except CancelledError:
            if not preparation_entered:
                await uncancel_then_cleanup(
                    finalize_preparation_cancelled(
                        api_context=failure_boundary.api_context,
                        stream_dependencies=failure_boundary.stream_dependencies,
                        chat_streams=chat_streams,
                        runtime=runtime,
                        placeholder_persisted=runtime.assistant_placeholder_persisted,
                        trace_id=trace_id,
                        logger=logger,
                    ),
                )
            raise

    execution_task = create_ephemeral_task(
        execute_owned_preparation(),
        name=f"ws-chat-stream-{runtime.conv_id}",
    )
    runtime.runner_task = execution_task

    def ensure_cancelled_task_finalized(completed_task: Task[None]) -> None:
        if not completed_task.cancelled() or execution_started:
            return

        async def finalize_if_still_registered() -> None:
            registered = await failure_boundary.api_context.dependencies.chat_stream_registry.get(
                user_id=runtime.user_id,
                conv_id=runtime.conv_id,
            )
            if registered is not runtime:
                return
            await finalize_preparation_cancelled(
                api_context=failure_boundary.api_context,
                stream_dependencies=failure_boundary.stream_dependencies,
                chat_streams=chat_streams,
                runtime=runtime,
                placeholder_persisted=runtime.assistant_placeholder_persisted,
                trace_id=trace_id,
                logger=logger,
            )

        finalizer_task = create_ephemeral_task(
            finalize_if_still_registered(),
            name=f"ws-chat-stream-cancel-finalizer-{runtime.conv_id}",
        )
        failure_boundary.api_context.dependencies.application_control.track_background_task(
            finalizer_task,
        )

    execution_task.add_done_callback(ensure_cancelled_task_finalized)
    failure_boundary.api_context.dependencies.application_control.track_background_task(
        execution_task,
    )
