"""SoAI - Non-streaming inference orchestration [backend/features/api/routes/openai/chat/non_streaming/runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from features.api.routes.openai.chat.non_streaming.loop import (
    run_non_streaming_result_loop,
)
from features.api.routes.openai.chat.non_streaming.subscription import (
    acquire_non_streaming_subscription,
)
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.openai_context.internal_protocols import (
        OpenAIApiContextProtocol,
    )

__all__ = ("wait_for_non_streaming_inference_result",)

LOGGER_NAME = "SoAI.features.api.non_streaming_runner"
OPERATION = "openai.chat.non_streaming.close_subscription"


async def wait_for_non_streaming_inference_result(
    api_context: OpenAIApiContextProtocol,
    *,
    stream_dependencies: StreamDependencies,
    registry: TaskRegistryProtocol,
    task: Task,
    reply_queue: asyncio.Queue[Event],
    context: RequestContext,
    request_json: JSONDict,
    required_capabilities: tuple[str, ...],
) -> JSONResponse:
    subscription_or_response = await acquire_non_streaming_subscription(
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        registry=registry,
        task=task,
        reply_queue=reply_queue,
        context=context,
    )
    if isinstance(subscription_or_response, JSONResponse):
        return subscription_or_response
    subscription = subscription_or_response
    logger = get_logger(LOGGER_NAME)
    listener_queue = subscription.queue
    try:
        return await run_non_streaming_result_loop(
            api_context,
            stream_dependencies=stream_dependencies,
            registry=registry,
            task=task,
            context=context,
            request_json=request_json,
            required_capabilities=required_capabilities,
            listener_queue=listener_queue,
        )
    finally:
        try:
            await uncancel_then_cleanup(subscription.close())
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="openai.chat.non_streaming.close_subscription",
            )
            log_handled_exception(
                logger,
                coerced,
                message="Failed to close non-streaming subscription (non-critical).",
                trace_id=context.trace_id,
                operation=OPERATION,
                level="debug",
                details={"task_id": task.task_id},
            )
