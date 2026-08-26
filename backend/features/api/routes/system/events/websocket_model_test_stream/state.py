"""SoAI - WebSocket model test stream state and event publishing [backend/features/api/routes/system/events/websocket_model_test_stream/state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.activity_payloads import build_activity_payload
from core.events.completion_waiting import (
    EventPublicationReceipt,
    publication_completion_deadline,
)
from core.events.types_system import ModelTestStreamEvent

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict

__all__ = (
    "ModelTestStreamRuntime",
    "publish_model_test_stream_event",
    "publish_model_test_stream_loading_activity",
    "publish_model_test_stream_loading_error",
)


@dataclass(slots=True)
class ModelTestStreamRuntime:
    run_id: str
    user_id: int
    started_at_ms: int
    next_sequence: int = 0
    active_task_id: str | None = None
    detach_event: asyncio.Event | None = None
    publish_lock: asyncio.Lock | None = None


async def publish_model_test_stream_event(
    event_bus: EventBusProtocol,
    runtime: ModelTestStreamRuntime,
    *,
    event_type: str,
    payload: JSONDict,
    wait: bool = True,
) -> None:
    if runtime.publish_lock is None:
        runtime.publish_lock = asyncio.Lock()
    async with runtime.publish_lock:
        sequence = runtime.next_sequence
        runtime.next_sequence += 1
        stream_event = ModelTestStreamEvent(
            user_id=runtime.user_id,
            run_id=runtime.run_id,
            sequence=sequence,
            event_type=event_type,
            payload=payload,
        )
        if wait:
            receipt = EventPublicationReceipt.create(
                event_type=type(stream_event).__name__,
                operation="api_system.websocket_model_test_stream_state.publish_model_test_stream_event",
            )
            await event_bus.publish(stream_event, wait_for_completion=receipt.completion_signal)
            await receipt.wait_for_completion(publication_completion_deadline())
            return
        await event_bus.publish(stream_event)


async def publish_model_test_stream_loading_error(
    event_bus: EventBusProtocol,
    runtime: ModelTestStreamRuntime,
    *,
    started_at_ms: int,
    duration_ms: int,
    reason: str | None,
    error_type: str,
) -> None:
    activity = build_activity_payload(
        status="error",
        started_at_ms=int(started_at_ms),
        duration_ms=max(0, int(duration_ms)),
        reason=reason,
        error_type=str(error_type or "server_error"),
    )
    await publish_model_test_stream_event(
        event_bus,
        runtime,
        event_type="loading",
        payload={"loading": activity},
    )


async def publish_model_test_stream_loading_activity(
    event_bus: EventBusProtocol,
    runtime: ModelTestStreamRuntime,
    *,
    status: str,
    duration_ms: int,
    reason: str | None,
    error_type: str | None,
) -> None:
    await publish_model_test_stream_event(
        event_bus,
        runtime,
        event_type="loading",
        payload={
            "loading": build_activity_payload(
                status=status,
                started_at_ms=int(runtime.started_at_ms),
                duration_ms=duration_ms,
                reason=reason,
                error_type=error_type,
            ),
        },
    )
