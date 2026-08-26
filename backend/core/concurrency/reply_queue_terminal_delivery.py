"""SoAI - Bounded terminal event delivery to reply queues [backend/core/concurrency/reply_queue_terminal_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol

__all__ = ("try_deliver_terminal_reply_event",)


async def try_deliver_terminal_reply_event(
    *,
    reply_queue: asyncio.Queue[Event],
    event: Event,
    timeout_seconds: float,
    logger: LoggerProtocol,
    operation: str,
) -> bool:
    try:
        await asyncio.wait_for(reply_queue.put(event), timeout=max(0.0, float(timeout_seconds)))
        return True
    except TimeoutError:
        logger.warning(
            "Terminal reply event delivery timed out after %.1fs (event=%s, operation=%s).",
            float(timeout_seconds),
            type(event).__name__,
            operation,
        )
        return False
