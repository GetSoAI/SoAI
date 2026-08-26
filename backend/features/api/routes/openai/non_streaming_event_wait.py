"""SoAI - Shared non-streaming event waiting with API error coercion [backend/features/api/routes/openai/non_streaming_event_wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.task_groups import QueueEventWaiter
from core.errors.error_types import ErrorType
from core.events.types_base import Event
from core.events.types_plugins import ErrorEvent
from core.runtime.protocols import RequestProtocol
from features.api.runtime.errors import raise_error_type, raise_service_unavailable
from features.api.streaming.types import StreamDependencies

__all__ = ("wait_for_non_streaming_event",)


async def wait_for_non_streaming_event(
    *,
    request: RequestProtocol,
    stream_dependencies: StreamDependencies,
    waiter: QueueEventWaiter[Event | None],
    timeout: float,
) -> Event:
    result_event = await waiter.wait(timeout=timeout)
    if result_event is None:
        if stream_dependencies.shutdown_event.is_set():
            raise_service_unavailable(request, "SoAI API Server is shutting down.")
        raise_service_unavailable(
            request,
            "Task stream closed before completion.",
            error_type=ErrorType.SERVER_ERROR.value,
        )
    if isinstance(result_event, ErrorEvent):
        raise_error_type(request, result_event.error_type, result_event.message)
    return result_event
