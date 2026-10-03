"""SoAI - Agent streaming assistant output publisher [backend/features/agent/runtime/streaming_assistant_output_publisher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from features.agent.events.types import AgentItemDeltaEvent
from features.agent.runtime.injected_prompt_echo_prefix_partition import (
    split_prefix_pending_frame,
)
from features.agent.runtime.injected_prompt_echo_stream_rewrite import (
    InjectedPromptEchoStreamRewriter,
)
from features.agent.runtime.injected_prompt_echo_stripping import (
    resolve_streaming_echo_prefix,
)
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
    content_index_base: int = 0
    text_parts: list[str] = field(default_factory=list[str])
    chunks: list[bytes] = field(default_factory=list[bytes])
    delta_batches: list[tuple[str, ...]] = field(default_factory=list[tuple[str, ...]])
    prefix_pending: bool = True
    prefix_removed_chars: int = 0
    prefix_raw_text_parts: list[str] = field(default_factory=list[str])
    prefix_chunks: list[bytes] = field(default_factory=list[bytes])
    prefix_rewriter: InjectedPromptEchoStreamRewriter | None = None

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
        if self.prefix_pending:
            immediate_frame, remaining_frame = split_prefix_pending_frame(chunk)
            if immediate_frame is not None:
                awaitable = self.on_bytes(immediate_frame)
                if awaitable is not None:
                    await awaitable
            if remaining_frame is not None:
                self.prefix_chunks.append(remaining_frame)
            return
        await self._publish_live_chunk(chunk)

    async def handle_visible_deltas(self, deltas: tuple[str, ...]) -> None:
        if self.buffer_output:
            if deltas:
                self.delta_batches.append(tuple(deltas))
            for delta in deltas:
                if delta:
                    self.text_parts.append(delta)
            return
        if self.prefix_pending:
            self.prefix_raw_text_parts.extend(delta for delta in deltas if delta)
            await self._resolve_live_prefix(terminal=False)
            return
        if self.on_visible_deltas is not None:
            maybe_awaitable = self.on_visible_deltas(deltas)
            if maybe_awaitable is not None:
                await maybe_awaitable
        await self.publish_visible_delta_events(deltas, record_text=True)

    async def finalize_live_prefix(self) -> None:
        if self.buffer_output:
            return
        if self.prefix_pending:
            await self._resolve_live_prefix(terminal=True)
        if self.prefix_rewriter is not None:
            self.prefix_rewriter.finalize()

    async def _resolve_live_prefix(self, *, terminal: bool) -> None:
        raw_text = "".join(self.prefix_raw_text_parts)
        decision = resolve_streaming_echo_prefix(raw_text, terminal=terminal)
        if decision is None:
            return
        self.prefix_pending = False
        self.prefix_removed_chars = (
            len(raw_text) - len(decision.sanitized_text) if decision.stripped else 0
        )
        if self.prefix_removed_chars:
            self.prefix_rewriter = InjectedPromptEchoStreamRewriter(
                removed_visible_text=raw_text[: self.prefix_removed_chars],
                content_index_base=self.content_index_base,
            )
        buffered_chunks = tuple(self.prefix_chunks)
        rewritten_chunks = (
            self.prefix_rewriter.rewrite_buffered_chunks(buffered_chunks)
            if self.prefix_rewriter is not None
            else buffered_chunks
        )
        for chunk in rewritten_chunks:
            awaitable = self.on_bytes(chunk)
            if awaitable is not None:
                await awaitable
        self.prefix_chunks.clear()
        visible_text = decision.sanitized_text if decision.stripped else raw_text
        if visible_text:
            if self.on_visible_deltas is not None:
                maybe_awaitable = self.on_visible_deltas((visible_text,))
                if maybe_awaitable is not None:
                    await maybe_awaitable
            await self.publish_visible_delta_events((visible_text,), record_text=True)
        self.prefix_raw_text_parts.clear()

    async def _publish_live_chunk(self, chunk: bytes) -> None:
        rewriter = self.prefix_rewriter
        rewritten_chunks = rewriter.feed(chunk) if rewriter is not None else (chunk,)
        for rewritten in rewritten_chunks:
            awaitable = self.on_bytes(rewritten)
            if awaitable is not None:
                await awaitable

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
