"""SoAI - Deferred tool call lifecycle streamer [backend/core/tool_calls/deferred_tool_call_streamer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.epoch import epoch_ms
from core.tool_calls.deferred_tool_call_events import (
    publish_deferred_tool_call_completed_event,
    publish_deferred_tool_call_started_event,
)
from core.tool_calls.deferred_tool_call_persistence import (
    persist_deferred_tool_call_running_state,
    persist_deferred_tool_call_terminal_state,
)
from core.tool_calls.deferred_tool_call_row import (
    DeferredToolCallIdentity,
    DeferredToolCallRow,
    create_deferred_tool_call_identity,
    load_deferred_tool_call_row_noncritical,
)
from core.tool_calls.status_values import (
    is_terminal_tool_call_status,
    normalize_tool_call_status,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "DeferredToolCallActivity",
    "DeferredToolCallDependencies",
    "DeferredToolCallStreamer",
)

OPERATION_DEFERRED_TOOL_CALL_PUBLISH_STARTED = "core.tool_calls.deferred_tool_call.publish_started"
OPERATION_DEFERRED_TOOL_CALL_PUBLISH_TERMINAL = (
    "core.tool_calls.deferred_tool_call.publish_terminal"
)


@dataclass(frozen=True, slots=True)
class DeferredToolCallDependencies:
    database_tool_calls: DatabaseToolCallsProtocol
    event_bus: EventBusProtocol
    logger: LoggerProtocol
    trace_id: str
    user_id: int
    conv_id: str
    assistant_turn_at_ms: int
    model_variant_index: int
    turn_id: str
    iteration_index: int
    call_id: str
    tool_name: str

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DeferredToolCallDependencies",
            database_tool_calls=self.database_tool_calls,
            event_bus=self.event_bus,
            logger=self.logger,
            trace_id=self.trace_id,
            user_id=self.user_id,
            conv_id=self.conv_id,
            assistant_turn_at_ms=self.assistant_turn_at_ms,
            model_variant_index=self.model_variant_index,
            turn_id=self.turn_id,
            iteration_index=self.iteration_index,
            call_id=self.call_id,
            tool_name=self.tool_name,
        )

    def build_identity(self) -> DeferredToolCallIdentity:
        return create_deferred_tool_call_identity(
            conv_id=self.conv_id,
            call_id=self.call_id,
            turn_id=self.turn_id,
            iteration_index=self.iteration_index,
            assistant_turn_at_ms=self.assistant_turn_at_ms,
            model_variant_index=self.model_variant_index,
        )


@dataclass(frozen=True, slots=True)
class DeferredToolCallActivity:
    storage_call_id: str
    streamer_deps: DeferredToolCallDependencies


@dataclass(slots=True)
class DeferredToolCallStreamer:
    deps: DeferredToolCallDependencies
    _tool_call_row: DeferredToolCallRow | None = None
    _started: bool = False
    _finalized: bool = False
    _transition_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def _load_tool_call_row(self) -> DeferredToolCallRow | None:
        if self._tool_call_row is not None:
            return self._tool_call_row
        row = await load_deferred_tool_call_row_noncritical(
            database_tool_calls=self.deps.database_tool_calls,
            logger=self.deps.logger,
            trace_id=self.deps.trace_id,
            identity=self.deps.build_identity(),
        )
        self._tool_call_row = row
        return row

    async def ensure_started(self) -> None:
        async with self._transition_lock:
            if self._finalized or self._started:
                return
            row = await self._load_tool_call_row()
            if row is None:
                return
            started_at_ms = epoch_ms()
            await persist_deferred_tool_call_running_state(
                database_tool_calls=self.deps.database_tool_calls,
                logger=self.deps.logger,
                trace_id=self.deps.trace_id,
                call_id=self.deps.call_id,
                row=row,
                started_at_ms=started_at_ms,
            )
            self._started = True
            try:
                await publish_deferred_tool_call_started_event(
                    event_bus=self.deps.event_bus,
                    row=row,
                    call_id=self.deps.call_id,
                    tool_name=self.deps.tool_name,
                    user_id=self.deps.user_id,
                    started_at_ms=started_at_ms,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_DEFERRED_TOOL_CALL_PUBLISH_STARTED,
                    trace_id=self.deps.trace_id,
                )
                log_handled_exception(
                    self.deps.logger,
                    coerced,
                    message="Failed to publish deferred tool call started event (non-critical).",
                    trace_id=self.deps.trace_id,
                    operation=OPERATION_DEFERRED_TOOL_CALL_PUBLISH_STARTED,
                    level="warning",
                    details={"call_id": self.deps.call_id},
                )

    async def finalize(
        self,
        *,
        status: str,
        duration_ms: int,
        error_message: str | None,
        result_payload: JSONValue | None,
    ) -> None:
        async with self._transition_lock:
            if self._finalized:
                return
            row = await self._load_tool_call_row()
            if row is None:
                return
            completed_at_ms = epoch_ms()
            persisted = await persist_deferred_tool_call_terminal_state(
                database_tool_calls=self.deps.database_tool_calls,
                logger=self.deps.logger,
                trace_id=self.deps.trace_id,
                call_id=self.deps.call_id,
                row=row,
                status=status,
                duration_ms=duration_ms,
                error_message=error_message,
                completed_at_ms=completed_at_ms,
                result_payload=result_payload,
            )
            self._finalized = True
            published = _resolve_published_terminal_fields(
                persisted,
                fallback_status=status,
                fallback_duration_ms=duration_ms,
                fallback_error_message=error_message,
                fallback_result_payload=result_payload,
            )
            try:
                await publish_deferred_tool_call_completed_event(
                    event_bus=self.deps.event_bus,
                    row=row,
                    call_id=self.deps.call_id,
                    tool_name=self.deps.tool_name,
                    user_id=self.deps.user_id,
                    status=published.status,
                    duration_ms=published.duration_ms,
                    error_message=published.error_message,
                    result_payload=published.result_payload,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_DEFERRED_TOOL_CALL_PUBLISH_TERMINAL,
                    trace_id=self.deps.trace_id,
                )
                log_handled_exception(
                    self.deps.logger,
                    coerced,
                    message="Failed to publish deferred tool call completion event (non-critical).",
                    trace_id=self.deps.trace_id,
                    operation=OPERATION_DEFERRED_TOOL_CALL_PUBLISH_TERMINAL,
                    level="warning",
                    details={"call_id": self.deps.call_id},
                )


@dataclass(frozen=True, slots=True)
class _PublishedTerminalFields:
    status: str
    duration_ms: int
    error_message: str | None
    result_payload: JSONValue | None


def _resolve_published_terminal_fields(
    persisted: JSONDict | None,
    *,
    fallback_status: str,
    fallback_duration_ms: int,
    fallback_error_message: str | None,
    fallback_result_payload: JSONValue | None,
) -> _PublishedTerminalFields:
    if persisted is None:
        return _PublishedTerminalFields(
            status=fallback_status,
            duration_ms=fallback_duration_ms,
            error_message=fallback_error_message,
            result_payload=fallback_result_payload,
        )
    persisted_status_value = persisted.get("status")
    persisted_status = normalize_tool_call_status(
        persisted_status_value if isinstance(persisted_status_value, str) else "",
    )
    status = persisted_status if is_terminal_tool_call_status(persisted_status) else fallback_status
    duration_value = persisted.get("duration_ms")
    duration_ms = (
        max(0, int(duration_value))
        if isinstance(duration_value, int) and not isinstance(duration_value, bool)
        else fallback_duration_ms
    )
    error_value = persisted.get("error")
    error_message = error_value if isinstance(error_value, str) else fallback_error_message
    return _PublishedTerminalFields(
        status=status,
        duration_ms=duration_ms,
        error_message=error_message,
        result_payload=persisted.get("result"),
    )
