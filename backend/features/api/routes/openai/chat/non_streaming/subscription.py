"""SoAI - Non-streaming inference stream subscription [backend/features/api/routes/openai/chat/non_streaming/subscription.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi.responses import JSONResponse

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.streaming.protocols import StreamSubscriptionProtocol
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from features.api.routes.openai.chat.non_streaming_failures import (
    complete_task_stream_unavailable,
)
from features.api.runtime.openai_context.internal_protocols import (
    OpenAIApiContextProtocol,
)
from features.api.streaming.types import StreamDependencies

__all__ = ("acquire_non_streaming_subscription",)

LOGGER_NAME = "SoAI.features.api.subscription"
OPERATION = "api_openai.handle_inference_request"


async def acquire_non_streaming_subscription(
    *,
    api_context: OpenAIApiContextProtocol,
    stream_dependencies: StreamDependencies,
    registry: TaskRegistryProtocol,
    task: Task,
    reply_queue: asyncio.Queue[Event],
    context: RequestContext,
) -> StreamSubscriptionProtocol | JSONResponse:
    try:
        subscription = await stream_dependencies.acquire_stream_subscription(
            reply_queue,
            task_id=task.task_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="api_openai.handle_inference_request",
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to acquire stream subscription for inference task.",
            trace_id=context.trace_id,
            operation=OPERATION,
            level="warning",
        )
        return await complete_task_stream_unavailable(
            api_context,
            registry=registry,
            task=task,
            context=context,
        )
    if subscription is None:
        log_exception(
            get_logger(LOGGER_NAME),
            StateError("Stream subscription was not created."),
            message="Stream subscription was not created for inference task.",
            trace_id=context.trace_id,
            operation=OPERATION,
            level="warning",
        )
        return await complete_task_stream_unavailable(
            api_context,
            registry=registry,
            task=task,
            context=context,
        )
    return subscription
