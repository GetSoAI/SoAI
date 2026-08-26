"""SoAI - Agentic SSE delivery acknowledgments [backend/features/api/streaming/agentic_sse_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass

from core.concurrency.wait_race import wait_for_awaitable_or_event

__all__ = (
    "AgenticSseDelivery",
    "acknowledge_agentic_sse_delivery",
    "build_agentic_sse_delivery",
    "drain_agentic_sse_delivery_queue",
    "release_agentic_sse_deliveries",
    "wait_for_agentic_sse_delivery_ack",
)


@dataclass(frozen=True, slots=True)
class AgenticSseDelivery:
    chunk: bytes
    acknowledged: asyncio.Future[None] | None


def build_agentic_sse_delivery(
    chunk: bytes,
    *,
    requires_ack: bool,
) -> AgenticSseDelivery:
    acknowledged = asyncio.get_running_loop().create_future() if requires_ack else None
    return AgenticSseDelivery(chunk=chunk, acknowledged=acknowledged)


def acknowledge_agentic_sse_delivery(delivery: AgenticSseDelivery) -> None:
    acknowledged = delivery.acknowledged
    if acknowledged is not None and not acknowledged.done():
        acknowledged.set_result(None)


def release_agentic_sse_deliveries(deliveries: Iterable[AgenticSseDelivery]) -> None:
    for delivery in deliveries:
        acknowledge_agentic_sse_delivery(delivery)


def drain_agentic_sse_delivery_queue(
    queue: asyncio.Queue[AgenticSseDelivery],
) -> list[AgenticSseDelivery]:
    deliveries: list[AgenticSseDelivery] = []
    while True:
        try:
            deliveries.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            return deliveries


async def _await_agentic_sse_delivery_ack(delivery: AgenticSseDelivery) -> None:
    acknowledged = delivery.acknowledged
    if acknowledged is not None:
        await acknowledged


async def wait_for_agentic_sse_delivery_ack(
    delivery: AgenticSseDelivery,
    detach_event: asyncio.Event,
) -> None:
    acknowledged = delivery.acknowledged
    if acknowledged is None or acknowledged.done():
        return
    await wait_for_awaitable_or_event(
        _await_agentic_sse_delivery_ack(delivery),
        detach_event,
    )
