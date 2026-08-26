"""SoAI - Streaming subscription utilities [backend/features/api/streaming/subscriptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.events.types_base import Event
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.validation.integers import is_strict_int
from features.api.streaming.internal_protocols import TaskIdContextProtocol
from features.api.streaming.types import StreamDependencies

__all__ = (
    "StreamClosedSentinel",
    "StreamKeepAliveSentinel",
    "StreamShutdownSentinel",
    "StreamTimeoutSentinel",
    "ensure_live_reply_queue",
    "resolve_task_id_from_sources",
)


class StreamTimeoutSentinel: ...


class StreamKeepAliveSentinel: ...


class StreamClosedSentinel: ...


class StreamShutdownSentinel: ...


def _resolve_attached_reply_queue_maxsize(stream_dependencies: StreamDependencies) -> int:
    configured_limit = stream_dependencies.config.get_int(
        "SERVER.HTTP.STREAMING.REPLAY_BUFFER_SIZE",
    )
    if is_strict_int(configured_limit) and configured_limit > 0:
        return int(configured_limit)
    return 1000


async def ensure_live_reply_queue(
    task: Task,
    *,
    task_registry: TaskRegistryProtocol,
    stream_dependencies: StreamDependencies,
) -> asyncio.Queue[Event] | None:
    if task.reply_queue is not None:
        return task.reply_queue
    if task.status.is_terminal():
        return None
    reply_queue: asyncio.Queue[Event] = asyncio.Queue(
        maxsize=_resolve_attached_reply_queue_maxsize(stream_dependencies),
    )
    attached_task = await task_registry.attach_reply_queue(task.task_id, reply_queue)
    if attached_task is None:
        return None
    return attached_task.reply_queue


def resolve_task_id_from_sources(
    context: TaskIdContextProtocol | None,
    reply_queue: asyncio.Queue[Event],
    *,
    task_registry: TaskRegistryProtocol,
) -> str | None:
    if context is None:
        raw_task_id = None
    else:
        try:
            raw_task_id = context.task_id
        except AttributeError:
            raw_task_id = None
    if isinstance(raw_task_id, str) and raw_task_id:
        return raw_task_id
    identity = task_registry.resolve_task_identity_for_reply_queue(reply_queue)
    if identity is not None:
        return identity[0]
    return None
