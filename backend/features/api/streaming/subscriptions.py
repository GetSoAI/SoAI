"""SoAI - Streaming subscription utilities [backend/features/api/streaming/subscriptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.events.types_base import Event
from core.tasks.protocols import TaskRegistryProtocol
from features.api.streaming.internal_protocols import TaskIdContextProtocol

__all__ = (
    "StreamClosedSentinel",
    "StreamKeepAliveSentinel",
    "StreamShutdownSentinel",
    "StreamTimeoutSentinel",
    "resolve_task_id_from_sources",
)


class StreamTimeoutSentinel: ...


class StreamKeepAliveSentinel: ...


class StreamClosedSentinel: ...


class StreamShutdownSentinel: ...


def resolve_task_id_from_sources(
    context: TaskIdContextProtocol | None,
    reply_queue: asyncio.Queue[Event],
    *,
    task_registry: TaskRegistryProtocol,
) -> str | None:
    identity = task_registry.resolve_task_identity_for_reply_queue(reply_queue)
    if identity is not None:
        return identity[0]
    if context is None:
        raw_task_id = None
    else:
        try:
            raw_task_id = context.task_id
        except AttributeError:
            raw_task_id = None
    if isinstance(raw_task_id, str) and raw_task_id:
        return raw_task_id
    return None
