"""SoAI - Structured subagent parent tool call update bridge [backend/features/agent/subagents/parent_tool_call_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.agent.status_values import SUBAGENT_STATUS_CANCELLED
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.epoch import epoch_ms
from core.tool_calls.deferred_tool_call_row import (
    DeferredToolCallRow,
    load_deferred_tool_call_row_noncritical,
)
from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallDependencies
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_ERROR,
    is_terminal_tool_call_status,
)
from core.validation.integers import is_strict_int
from features.agent.subagents.parent_tool_call_streaming import (
    SubagentParentToolCallStreamer,
)
from features.agent.subagents.parent_tool_call_text_blocks import (
    SubagentTextBlockBuffer,
)
from features.agent.subagents.parent_tool_call_update_models import (
    ChildToolCallState,
    build_subagent_parent_tool_result,
    normalize_result_with_output_delta,
    order_child_tool_call_payloads,
)
from features.agent.subagents.parent_tool_call_update_publishing import (
    publish_parent_tool_call_updated_event_noncritical,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("SubagentParentToolCallUpdateBridge",)

OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_LIVE = "agent.subagents.parent_tool_call_updates.live"
OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_FINALIZE = (
    "agent.subagents.parent_tool_call_updates.finalize"
)


@dataclass(slots=True)
class SubagentParentToolCallUpdateBridge:
    deps: DeferredToolCallDependencies
    _streamer: SubagentParentToolCallStreamer | None = None
    _tool_call_row: DeferredToolCallRow | None = None
    _latest_subagent_record: JSONDict | None = None
    _child_tool_calls_by_id: dict[str, ChildToolCallState] = field(
        default_factory=dict[str, ChildToolCallState],
    )
    _next_child_tool_call_order: int = 0
    _text_blocks: SubagentTextBlockBuffer = field(default_factory=SubagentTextBlockBuffer)
    _next_stream_order: int = 0
    _mutation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _is_closed: bool = False

    def _ensure_streamer(self) -> SubagentParentToolCallStreamer:
        if self._streamer is not None:
            return self._streamer
        self._streamer = SubagentParentToolCallStreamer(deps=self.deps)
        return self._streamer

    async def _load_tool_call_row(self) -> DeferredToolCallRow | None:
        if self._tool_call_row is not None:
            return self._tool_call_row
        self._tool_call_row = await load_deferred_tool_call_row_noncritical(
            database_tool_calls=self.deps.database_tool_calls,
            logger=self.deps.logger,
            trace_id=self.deps.trace_id,
            identity=self.deps.build_identity(),
        )
        return self._tool_call_row

    def _resolve_child_tool_call_payloads(self) -> list[JSONDict]:
        return order_child_tool_call_payloads(list(self._child_tool_calls_by_id.values()))

    def _resolve_result_payload(self) -> JSONDict:
        return build_subagent_parent_tool_result(
            subagent_record=self._latest_subagent_record,
            child_tool_calls=self._resolve_child_tool_call_payloads(),
            text_blocks=self._text_blocks.get_all(self._next_stream_order),
        )

    async def _publish_update_noncritical(self, *, ensure_started: bool) -> None:
        try:
            if self._is_closed:
                return
            if self._latest_subagent_record is None:
                return
            result_payload = self._resolve_result_payload()
            if ensure_started:
                streamer = self._ensure_streamer()
                await streamer.ensure_started()
            row = await self._load_tool_call_row()
            if row is None:
                return
            await publish_parent_tool_call_updated_event_noncritical(
                deps=self.deps,
                row=row,
                result_payload=result_payload,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self.deps.logger,
                exception,
                message="Failed to publish structured parent tool call live update for subagent (non-critical).",
                trace_id=self.deps.trace_id,
                operation=OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_LIVE,
                level="warning",
                details={"call_id": self.deps.call_id},
            )

    async def publish_subagent_state_noncritical(self, *, subagent_record: JSONDict) -> None:
        async with self._mutation_lock:
            if self._is_closed:
                return
            self._latest_subagent_record = dict(subagent_record)
            await self._publish_update_noncritical(ensure_started=True)

    async def publish_initial_subagent_state_noncritical(
        self,
        *,
        subagent_record: JSONDict,
    ) -> None:
        async with self._mutation_lock:
            if self._is_closed:
                return
            self._latest_subagent_record = dict(subagent_record)
            await self._publish_update_noncritical(ensure_started=False)

    async def add_text_block_delta(self, text: str, started_at_ms: int) -> None:
        if not text:
            return
        async with self._mutation_lock:
            if self._is_closed:
                return
            self._text_blocks.add_delta(text, started_at_ms)

    async def seed_subagent_state_noncritical(
        self,
        *,
        subagent_record: JSONDict,
    ) -> None:
        async with self._mutation_lock:
            if self._is_closed:
                return
            self._latest_subagent_record = dict(subagent_record)

    async def publish_child_tool_call_update_noncritical(
        self,
        *,
        call_id: str,
        tool_name: str,
        sequence_index: int | None,
        content_index_before: int | None,
        started_at_ms: int | None,
        duration_ms: int | None,
        status: str | None,
        arguments_payload: JSONValue | None,
        result_payload: JSONValue | None,
        code_diffs: list[JSONDict] | None,
        error_message: str | None,
        output_delta: str | None,
    ) -> None:
        normalized_call_id = str(call_id or "").strip()
        normalized_tool_name = str(tool_name or "").strip()
        if not normalized_call_id or not normalized_tool_name:
            return
        async with self._mutation_lock:
            if self._is_closed:
                return
            existing = self._child_tool_calls_by_id.get(normalized_call_id)
            if existing is None:
                if not is_strict_int(content_index_before) or content_index_before < 0:
                    return
                self._next_stream_order = self._text_blocks.close_current(self._next_stream_order)
                resolved_sequence_index = (
                    int(sequence_index)
                    if is_strict_int(sequence_index) and sequence_index >= 0
                    else self._next_child_tool_call_order
                )
                resolved_started_at_ms = (
                    int(started_at_ms)
                    if is_strict_int(started_at_ms) and started_at_ms >= 0
                    else epoch_ms()
                )
                existing = ChildToolCallState(
                    call_id=normalized_call_id,
                    tool_name=normalized_tool_name,
                    order_index=self._next_child_tool_call_order,
                    stream_order=self._next_stream_order,
                    content_index_before=int(content_index_before),
                    sequence_index=resolved_sequence_index,
                    started_at_ms=resolved_started_at_ms,
                )
                self._next_child_tool_call_order += 1
                self._next_stream_order += 1
                self._child_tool_calls_by_id[normalized_call_id] = existing
            existing.tool_name = normalized_tool_name
            if is_strict_int(content_index_before) and content_index_before >= 0:
                existing.content_index_before = int(content_index_before)
            if is_strict_int(sequence_index) and sequence_index >= 0:
                existing.sequence_index = int(sequence_index)
            if is_strict_int(started_at_ms) and started_at_ms >= 0:
                existing.started_at_ms = int(started_at_ms)
            if is_strict_int(duration_ms) and duration_ms >= 0:
                existing.duration_ms = int(duration_ms)
            if isinstance(status, str) and status.strip():
                existing.status = status.strip()
            if arguments_payload is not None:
                existing.arguments = arguments_payload
            if result_payload is not None:
                existing.result = result_payload
            if code_diffs is not None:
                existing.code_diffs = [dict(entry) for entry in code_diffs]
            if isinstance(error_message, str) and error_message.strip():
                existing.error = error_message.strip()
            if isinstance(output_delta, str) and output_delta:
                existing.result = normalize_result_with_output_delta(existing.result, output_delta)
            await self._publish_update_noncritical(ensure_started=True)

    async def finalize_noncritical(
        self,
        *,
        subagent_status: str,
        duration_ms: int,
        error_message: str | None,
        subagent_record: JSONDict | None,
    ) -> None:
        async with self._mutation_lock:
            if self._is_closed:
                return
            self._next_stream_order = self._text_blocks.close_current(self._next_stream_order)
            if subagent_record is not None:
                self._latest_subagent_record = dict(subagent_record)
                self._next_stream_order = self._text_blocks.ensure_terminal_from_subagent_record(
                    self._latest_subagent_record,
                    self._next_stream_order,
                )
            child_terminal_status = (
                TOOL_CALL_STATUS_CANCELLED
                if subagent_status == SUBAGENT_STATUS_CANCELLED
                else TOOL_CALL_STATUS_ERROR
            )
            terminal_timestamp_ms = epoch_ms()
            for child_tool_call in self._child_tool_calls_by_id.values():
                if is_terminal_tool_call_status(child_tool_call.status):
                    continue
                child_tool_call.status = child_terminal_status
                child_started_at_ms = (
                    int(child_tool_call.started_at_ms)
                    if is_strict_int(child_tool_call.started_at_ms)
                    and child_tool_call.started_at_ms >= 0
                    else terminal_timestamp_ms
                )
                child_tool_call.duration_ms = max(
                    0,
                    terminal_timestamp_ms - child_started_at_ms,
                )
                child_tool_call.error = (
                    "Subagent cancelled before the child tool call completed."
                    if child_terminal_status == TOOL_CALL_STATUS_CANCELLED
                    else "Subagent finished before the child tool call completed."
                )
            try:
                await self._ensure_streamer().finalize(
                    subagent_status=subagent_status,
                    duration_ms=max(0, int(duration_ms)),
                    error_message=error_message,
                    token_usage=None,
                    result_payload=self._resolve_result_payload(),
                )
                self._is_closed = True
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self.deps.logger,
                    exception,
                    message="Failed to finalize structured parent tool call for subagent (non-critical).",
                    trace_id=self.deps.trace_id,
                    operation=OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_FINALIZE,
                    level="warning",
                    details={"call_id": self.deps.call_id},
                )
