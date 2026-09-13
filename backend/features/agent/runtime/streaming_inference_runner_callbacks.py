"""SoAI - Shared streaming inference runner callback builders and assembly [backend/features/agent/runtime/streaming_inference_runner_callbacks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING

from core.events.types_base import Event
from core.openai.model_output_contract_errors import (
    is_invalid_tool_call_json_contract_error,
)
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.openai.token_accounting import (
    build_prompt_occupancy_metadata,
    count_prompt_occupancy_async,
)
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.request_sources import RequestSource
from core.streaming.protocols import StreamGeneratorStateProtocol
from core.tasks.task import Task
from core.tasks.type_catalog import TaskTypeId
from features.agent.internal_protocols import AgentStreamingInferenceRunnerProtocol
from features.agent.runtime.streaming_inference_admission import (
    create_streaming_inference_task,
)
from features.agent.runtime.streaming_inference_runner import (
    StreamingInferenceRunner,
    StreamingInferenceRunnerCallbacks,
)
from features.agent.runtime.streaming_inference_stream_generator import (
    build_agent_stream_generator,
)
from features.api.streaming.task_quota_metadata import resolve_task_stream_model

if TYPE_CHECKING:
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.tasks.protocols_cancellation import CancellationHistoryProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.streaming_iteration_session import (
        StreamingIterationSession,
    )
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("build_agent_streaming_inference_runner",)


def _build_stream_transcript(task: Task, model: str | None) -> OpenAIStreamTranscript:
    return OpenAIStreamTranscript(model_hint=resolve_task_stream_model(task, model))


def _build_runner_cancel_callbacks(
    cancellation_history: CancellationHistoryProtocol | None,
) -> tuple[
    Callable[[str, tuple[str, str]], Awaitable[bool]],
    Callable[[str], Awaitable[tuple[bool, str | None]]],
]:
    async def should_skip_error_chunk(
        effective_cancellation_id: str,
        parsed_error: tuple[str, str],
    ) -> bool:
        message, error_type = parsed_error
        if is_invalid_tool_call_json_contract_error(message=message, error_type=error_type):
            return True
        if cancellation_history is None:
            return False
        return await cancellation_history.is_cancelled(effective_cancellation_id)

    async def read_cancel_state(effective_cancellation_id: str) -> tuple[bool, str | None]:
        if cancellation_history is None:
            return (False, None)
        cancelled = await cancellation_history.is_cancelled(effective_cancellation_id)
        if not cancelled:
            return (False, None)
        return (
            True,
            await cancellation_history.get_reason(effective_cancellation_id),
        )

    return (should_skip_error_chunk, read_cancel_state)


def _resolve_stream_id(
    iteration_session: StreamingIterationSession,
    _payload_value: JSONDict | None,
) -> str | None:
    return iteration_session.iteration_state.root_stream_id


def build_agent_streaming_inference_runner(
    api_dependencies: ApiDependencies,
    *,
    context: RequestContext,
    initial_task: Task | None,
    initial_reply_queue: asyncio.Queue[Event] | None,
    task_type: TaskTypeId,
    user_id: int,
    owner_type: str,
    owner_id: str,
    metadata: JSONDict,
    model: str | None,
    request_source: RequestSource,
    token_estimation_profile: TokenEstimationProfile | None = None,
    cancellation_history: CancellationHistoryProtocol | None = None,
    on_task_ready: Callable[[Task, int], Awaitable[None] | None] | None = None,
    build_context: Callable[[RequestContext, str, int, str | None], RequestContext] | None = None,
    create_additional_task: (
        Callable[
            [
                JSONDict,
                RequestContext,
                str,
                Callable[[bytes], Awaitable[None] | None],
            ],
            Awaitable[tuple[Task, asyncio.Queue[Event]]],
        ]
        | None
    ) = None,
    stream_generator_factory: (
        Callable[
            [
                asyncio.Queue[Event],
                RequestContext,
                Task,
                StreamGeneratorStateProtocol,
                OpenAIStreamTranscript,
            ],
            AsyncIterator[bytes],
        ]
        | None
    ) = None,
) -> AgentStreamingInferenceRunnerProtocol:
    resolved_cancellation_history = (
        cancellation_history
        if cancellation_history is not None
        else api_dependencies.cancellation_history
    )
    resolved_token_estimation_profile = (
        token_estimation_profile
        if token_estimation_profile is not None
        else api_dependencies.prompt_token_counter.default_profile()
    )

    async def create_additional_task_default(
        payload: JSONDict,
        iteration_context: RequestContext,
        effective_cancellation_id: str,
        _on_bytes: Callable[[bytes], Awaitable[None] | None],
    ) -> tuple[Task, asyncio.Queue[Event]]:
        task_metadata = dict(metadata)
        task_metadata.update(
            build_prompt_occupancy_metadata(
                await count_prompt_occupancy_async(
                    prompt_token_counter=api_dependencies.prompt_token_counter,
                    request_payload=payload,
                    token_estimation_profile=resolved_token_estimation_profile,
                ),
            ),
        )
        bundle = await create_streaming_inference_task(
            api_dependencies,
            context=iteration_context,
            request_json=payload,
            task_type=task_type,
            user_id=user_id,
            owner_type=owner_type,
            owner_id=owner_id,
            cancellation_id=effective_cancellation_id,
            metadata=task_metadata,
            request_source=request_source,
        )
        return (bundle.task, bundle.reply_queue)

    def build_context_default(
        base_context: RequestContext,
        cancellation_id: str,
        agent_iteration_index: int,
        task_id: str | None,
    ) -> RequestContext:
        return clone_request_context(
            base_context,
            task_id=task_id,
            cancellation_id=cancellation_id,
            agent_iteration_index=agent_iteration_index,
        )

    resolved_build_context = build_context if build_context is not None else build_context_default
    resolved_create_additional_task = (
        create_additional_task
        if create_additional_task is not None
        else create_additional_task_default
    )

    def create_stream_transcript(task: Task) -> OpenAIStreamTranscript:
        return _build_stream_transcript(task, model)

    def create_stream_bytes_generator_default(
        reply_queue: asyncio.Queue[Event],
        stream_context: RequestContext,
        task: Task,
        stream_state: StreamGeneratorStateProtocol,
        stream_transcript: OpenAIStreamTranscript,
    ) -> AsyncGenerator[bytes]:
        return build_agent_stream_generator(
            api_dependencies,
            context=stream_context,
            task=task,
            reply_queue=reply_queue,
            model=model,
            include_usage=False,
            emit_done_marker=False,
            stream_transcript=stream_transcript,
            stream_result_state=stream_state,
        )

    resolved_create_stream_generator = (
        stream_generator_factory
        if stream_generator_factory is not None
        else create_stream_bytes_generator_default
    )
    should_skip_error_chunk, read_cancel_state = _build_runner_cancel_callbacks(
        resolved_cancellation_history,
    )
    return StreamingInferenceRunner(
        context=context,
        initial_task=initial_task,
        initial_reply_queue=initial_reply_queue,
        callbacks=StreamingInferenceRunnerCallbacks(
            build_context=resolved_build_context,
            create_additional_task=resolved_create_additional_task,
            create_stream_generator=resolved_create_stream_generator,
            create_stream_transcript=create_stream_transcript,
            on_task_ready=on_task_ready,
            should_skip_error_chunk=should_skip_error_chunk,
            read_cancel_state=read_cancel_state,
            resolve_stream_id=_resolve_stream_id,
        ),
    )
