"""SoAI - Agentic SSE output delivery bridge [backend/features/api/streaming/agentic_sse_output_bridge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.concurrency.queue_backpressure import (
    BackpressureDeliveryStatus,
    put_with_backpressure,
)
from core.concurrency.wait_race import WaitRaceOutcome, wait_for_queue_or_event
from core.errors.exceptions import StateError
from features.api.streaming.agentic_sse_delivery import (
    AgenticSseDelivery,
    acknowledge_agentic_sse_delivery,
    build_agentic_sse_delivery,
    drain_agentic_sse_delivery_queue,
    release_agentic_sse_deliveries,
    wait_for_agentic_sse_delivery_ack,
)
from features.api.streaming.agentic_sse_engine_task_lifecycle import (
    settle_engine_task_after_stream_exit,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger

__all__ = ("AgenticSseOutputBridge",)

STREAM_QUEUE_SIZE: int = 512
STREAM_QUEUE_BACKPRESSURE_TIMEOUT_SECONDS: float = 30.0
STREAM_QUEUE_OUTPUT_CONTRACT_ERROR = "Agentic SSE stream queue yielded an invalid delivery."


@dataclass(slots=True)
class AgenticSseOutputBridge:
    logger: TraceLogger
    done_chunk: bytes
    acknowledge_stream_consumption: bool
    stream_queue: asyncio.Queue[AgenticSseDelivery] = field(init=False)
    detach_event: asyncio.Event = field(init=False)
    stream_stop_event: asyncio.Event = field(init=False)

    def __post_init__(self) -> None:
        self.stream_queue = asyncio.Queue(maxsize=STREAM_QUEUE_SIZE)
        self.detach_event = asyncio.Event()
        self.stream_stop_event = asyncio.Event()

    async def push_bytes(self, chunk: bytes) -> None:
        if self.detach_event.is_set():
            return
        stream_delivery = build_agentic_sse_delivery(
            chunk,
            requires_ack=self.acknowledge_stream_consumption and chunk != self.done_chunk,
        )
        delivery = await put_with_backpressure(
            self.stream_queue,
            stream_delivery,
            self.detach_event,
            overwrite_attempts=0,
            backpressure_timeout=STREAM_QUEUE_BACKPRESSURE_TIMEOUT_SECONDS,
        )
        if delivery.status in (
            BackpressureDeliveryStatus.DELIVERED,
            BackpressureDeliveryStatus.DELIVERED_AFTER_WAIT,
        ):
            await wait_for_agentic_sse_delivery_ack(stream_delivery, self.detach_event)
            return
        if delivery.status is BackpressureDeliveryStatus.SHUTDOWN:
            acknowledge_agentic_sse_delivery(stream_delivery)
            return
        self.detach_event.set()
        self.stream_stop_event.set()
        acknowledge_agentic_sse_delivery(stream_delivery)
        self.logger.debug("Detaching agentic stream output due to backpressure timeout.")

    async def stream_bytes(
        self,
        *,
        engine_task: asyncio.Task[None],
        cancel_engine_on_detach: bool,
        trace_id: str,
    ) -> AsyncGenerator[bytes]:
        stream_completed = False
        try:
            while True:
                delivery_value = await self._next_delivery(engine_task)
                if delivery_value is None:
                    stream_completed = (
                        engine_task.done()
                        and self.stream_queue.empty()
                        and not self.detach_event.is_set()
                    )
                    break
                chunk = delivery_value.chunk
                try:
                    yield chunk
                finally:
                    acknowledge_agentic_sse_delivery(delivery_value)
                if chunk == self.done_chunk:
                    stream_completed = True
                    break
        finally:
            release_agentic_sse_deliveries(drain_agentic_sse_delivery_queue(self.stream_queue))
            await settle_engine_task_after_stream_exit(
                engine_task=engine_task,
                detach_event=self.detach_event,
                stream_stop_event=self.stream_stop_event,
                cancel_engine_on_detach=cancel_engine_on_detach,
                stream_completed=stream_completed,
                logger=self.logger,
                trace_id=trace_id,
            )

    async def _next_delivery(self, engine_task: asyncio.Task[None]) -> AgenticSseDelivery | None:
        while True:
            if self.detach_event.is_set():
                return None
            if engine_task.done() and self.stream_queue.empty():
                return None
            race_result = await wait_for_queue_or_event(self.stream_queue, self.stream_stop_event)
            if race_result.outcome is WaitRaceOutcome.EVENT_TRIGGERED:
                if self.detach_event.is_set():
                    return None
                try:
                    event_delivery = self.stream_queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue
                if not isinstance(event_delivery, AgenticSseDelivery):
                    raise StateError(STREAM_QUEUE_OUTPUT_CONTRACT_ERROR)
                return event_delivery
            queued_delivery = race_result.value
            if not isinstance(queued_delivery, AgenticSseDelivery):
                raise StateError(STREAM_QUEUE_OUTPUT_CONTRACT_ERROR)
            return queued_delivery
