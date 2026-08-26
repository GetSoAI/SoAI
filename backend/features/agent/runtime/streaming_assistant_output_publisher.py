"""SoAI - Agent streaming assistant output publisher [backend/features/agent/runtime/streaming_assistant_output_publisher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from features.agent.events.types import AgentItemDeltaEvent
from features.agent.runtime.item_event_factories import (
    build_agent_assistant_item_started_event,
)
from features.agent.runtime.openai_payload import resolve_payload_model
from features.agent.runtime.streaming_retry_output_sse import (
    build_retry_stop_sse_bytes,
    build_retry_text_delta_sse_bytes,
    resolve_retry_stream_id,
)
from features.agent.runtime.turn_engine import publish_agent_event

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("StreamingAssistantOutputPublisher",)


@dataclass(slots=True)
class StreamingAssistantOutputPublisher:
    event_bus: EventBusProtocol | None
    logger: LoggerProtocol
    payload: JSONDict
    conv_id: str
    user_id: int
    turn_id: str
    item_id: str
    iteration_index: int
    buffer_output: bool
    next_action_sequence: Callable[[], Awaitable[int]]
    on_bytes: Callable[[bytes], Awaitable[None] | None]
    on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None
    text_parts: list[str] = field(default_factory=list[str])
    chunks: list[bytes] = field(default_factory=list[bytes])
    delta_batches: list[tuple[str, ...]] = field(default_factory=list[tuple[str, ...]])

    async def publish_item_started_event(self) -> None:
        await publish_agent_event(
            event_bus=self.event_bus,
            logger=self.logger,
            event_obj=build_agent_assistant_item_started_event(
                self.user_id,
                self.conv_id,
                self.turn_id,
                self.item_id,
                self.iteration_index,
                await self.next_action_sequence(),
            ),
        )

    async def handle_bytes(self, chunk: bytes) -> None:
        if self.buffer_output:
            self.chunks.append(bytes(chunk))
            return
        awaitable = self.on_bytes(chunk)
        if awaitable is not None:
            await awaitable

    async def handle_visible_deltas(self, deltas: tuple[str, ...]) -> None:
        if self.buffer_output:
            if deltas:
                self.delta_batches.append(tuple(deltas))
            for delta in deltas:
                if delta:
                    self.text_parts.append(delta)
            return
        if self.on_visible_deltas is not None:
            maybe_awaitable = self.on_visible_deltas(deltas)
            if maybe_awaitable is not None:
                await maybe_awaitable
        await self.publish_visible_delta_events(deltas, record_text=True)

    async def publish_visible_delta_events(
        self,
        deltas: tuple[str, ...],
        *,
        record_text: bool,
    ) -> None:
        for delta in deltas:
            if not delta:
                continue
            if record_text:
                self.text_parts.append(delta)
            await publish_agent_event(
                event_bus=self.event_bus,
                logger=self.logger,
                event_obj=AgentItemDeltaEvent(
                    user_id=self.user_id,
                    conv_id=self.conv_id,
                    turn_id=self.turn_id,
                    item_id=self.item_id,
                    iteration_index=self.iteration_index,
                    sequence=await self.next_action_sequence(),
                    text_delta=delta,
                ),
            )

    async def flush_buffered_output(self) -> None:
        for chunk in self.chunks:
            awaitable = self.on_bytes(chunk)
            if awaitable is not None:
                await awaitable
        for deltas in self.delta_batches:
            if self.on_visible_deltas is not None:
                maybe_awaitable = self.on_visible_deltas(deltas)
                if maybe_awaitable is not None:
                    await maybe_awaitable
            await self.publish_visible_delta_events(deltas, record_text=False)

    async def publish_repaired_output(self, text: str, stream_id: str | None) -> str:
        model = resolve_payload_model(self.payload)
        resolved_stream_id = resolve_retry_stream_id(stream_id)
        awaitable = self.on_bytes(
            build_retry_text_delta_sse_bytes(
                stream_id=resolved_stream_id,
                model=model,
                text_delta=text,
            ),
        )
        if awaitable is not None:
            await awaitable
        stop_awaitable = self.on_bytes(
            build_retry_stop_sse_bytes(
                stream_id=resolved_stream_id,
                model=model,
            ),
        )
        if stop_awaitable is not None:
            await stop_awaitable
        if self.on_visible_deltas is not None:
            maybe_awaitable = self.on_visible_deltas((text,))
            if maybe_awaitable is not None:
                await maybe_awaitable
        await self.publish_visible_delta_events((text,), record_text=False)
        return resolved_stream_id

    def buffered_text(self) -> str:
        return "".join(self.text_parts)

    def has_buffered_chunks(self) -> bool:
        return bool(self.chunks)

    def buffered_text_equals(self, text: str) -> bool:
        return self.buffered_text() == text
