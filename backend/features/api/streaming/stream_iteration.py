"""SoAI - Classified stream event iterator [backend/features/api/streaming/stream_iteration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum, auto

from core.events.types_base import Event
from core.runtime.protocols import RequestContextProtocol
from features.api.streaming.reply_queue_stream import iter_reply_queue_events
from features.api.streaming.subscriptions import (
    StreamClosedSentinel,
    StreamKeepAliveSentinel,
    StreamShutdownSentinel,
    StreamTimeoutSentinel,
)
from features.api.streaming.terminal_events import is_terminal_task_stream_event
from features.api.streaming.types import StreamDependencies

__all__ = (
    "StreamEvent",
    "StreamKeepalive",
    "StreamTermination",
    "StreamTerminationReason",
    "classify_sentinel",
    "classify_stream_event",
    "iter_classified_stream_events",
    "iter_openai_sse_classified_stream_events",
    "iter_openai_sse_classified_stream_events_with_keepalive_chunks",
)


class StreamTerminationReason(Enum):
    TIMEOUT = auto()
    SHUTDOWN = auto()
    CLOSED = auto()
    UNEXPECTED = auto()


@dataclass(frozen=True, slots=True)
class StreamKeepalive: ...


@dataclass(frozen=True, slots=True)
class StreamEvent[TEvent]:
    event: TEvent
    is_terminal: bool


@dataclass(frozen=True, slots=True)
class StreamTermination:
    reason: StreamTerminationReason
    message: str | None = None
    error_code: str | None = None


def classify_sentinel(
    item: (
        Event
        | type[StreamTimeoutSentinel]
        | type[StreamKeepAliveSentinel]
        | type[StreamClosedSentinel]
        | type[StreamShutdownSentinel]
    ),
) -> StreamTermination | None:
    if item is StreamTimeoutSentinel:
        return StreamTermination(
            reason=StreamTerminationReason.TIMEOUT,
            message="Stream timed out.",
            error_code="timeout_error",
        )
    if item is StreamShutdownSentinel:
        return StreamTermination(
            reason=StreamTerminationReason.SHUTDOWN,
            message="SoAI API Server is shutting down.",
            error_code="cancelled",
        )
    if item is StreamClosedSentinel:
        return StreamTermination(
            reason=StreamTerminationReason.CLOSED,
        )
    return None


def classify_stream_event(
    item: (
        Event
        | type[StreamTimeoutSentinel]
        | type[StreamKeepAliveSentinel]
        | type[StreamClosedSentinel]
        | type[StreamShutdownSentinel]
    ),
) -> StreamEvent[Event] | StreamTermination:
    sentinel_result = classify_sentinel(item)
    if sentinel_result is not None:
        return sentinel_result
    if not isinstance(item, Event):
        return StreamTermination(
            reason=StreamTerminationReason.UNEXPECTED,
            message="Stream closed.",
            error_code="server_error",
        )
    is_terminal = is_terminal_task_stream_event(item)
    return StreamEvent(event=item, is_terminal=is_terminal)


async def iter_classified_stream_events(
    reply_queue: asyncio.Queue[Event],
    stream_dependencies: StreamDependencies,
    context: RequestContextProtocol | None,
    *,
    publish_cancel_command: bool = True,
    close_on_timeout: bool = True,
) -> AsyncGenerator[StreamKeepalive | StreamEvent[Event] | StreamTermination]:
    inner_iter = iter_reply_queue_events(
        reply_queue,
        stream_dependencies,
        context,
        publish_cancel_command=publish_cancel_command,
        close_on_timeout=close_on_timeout,
    )
    try:
        async for item in inner_iter:
            if item is StreamKeepAliveSentinel:
                yield StreamKeepalive()
                continue
            classified = classify_stream_event(item)
            yield classified
            if isinstance(classified, StreamTermination):
                break
            if isinstance(classified, StreamEvent) and classified.is_terminal:
                break
    finally:
        await inner_iter.aclose()


def iter_openai_sse_classified_stream_events(
    reply_queue: asyncio.Queue[Event],
    stream_dependencies: StreamDependencies,
    context: RequestContextProtocol | None,
) -> AsyncGenerator[StreamKeepalive | StreamEvent[Event] | StreamTermination]:
    return iter_classified_stream_events(
        reply_queue,
        stream_dependencies,
        context,
        publish_cancel_command=True,
        close_on_timeout=True,
    )


async def iter_openai_sse_classified_stream_events_with_keepalive_chunks(
    reply_queue: asyncio.Queue[Event],
    stream_dependencies: StreamDependencies,
    context: RequestContextProtocol | None,
    *,
    keepalive_chunk: bytes,
) -> AsyncGenerator[bytes | StreamEvent[Event] | StreamTermination]:
    async for classified in iter_openai_sse_classified_stream_events(
        reply_queue,
        stream_dependencies,
        context,
    ):
        if isinstance(classified, StreamKeepalive):
            yield keepalive_chunk
            continue
        yield classified
