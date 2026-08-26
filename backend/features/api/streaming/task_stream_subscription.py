"""SoAI - Task stream subscription handle [backend/features/api/streaming/task_stream_subscription.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from features.api.streaming.internal_protocols import TaskStreamChannelProtocol

if TYPE_CHECKING:
    from core.events.types_base import Event

__all__ = ("StreamSubscription",)


class StreamSubscription:
    __slots__ = ("channel", "is_closed", "listener_id", "queue")

    def __init__(
        self,
        channel: TaskStreamChannelProtocol,
        listener_id: str,
        queue: asyncio.Queue[Event | None],
    ) -> None:
        self.channel = channel
        self.listener_id = listener_id
        self.queue = queue
        self.is_closed = False

    async def close(self) -> None:
        if self.is_closed:
            return
        self.is_closed = True
        await self.channel.unregister_listener(self.listener_id)
