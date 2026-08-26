"""SoAI - Responses passthrough persistence helpers [backend/features/api/routes/openai/responses/streaming_generator/passthrough_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.errors.exceptions import ValidationError
from core.openai.responses_events import build_failed_response_event
from core.openai.sse_events import format_openai_sse_data
from core.timing.durations import ms_to_seconds_floor
from core.timing.epoch import epoch_ms
from core.timing.monotonic import monotonic_ms
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from features.api.routes.openai.responses.response_event_storage import (
    ResponseStorageTarget,
    StoredResponseEvent,
    normalize_stored_response_event,
)
from features.api.routes.openai.responses.streaming_generator.persistence import (
    build_failed_event_bytes,
)
from features.api.runtime.context import ApiContext

__all__ = ("ResponsesPassthroughPersistence",)

DEFAULT_RESPONSES_PERSIST_FLUSH_INTERVAL_MS = 100
DEFAULT_RESPONSES_PERSIST_MAX_EVENTS_PER_FLUSH = 250
DEFAULT_RESPONSES_PERSIST_MAX_PENDING_EVENTS = 5000


@dataclass(slots=True)
class ResponsesPassthroughPersistence:
    api_context: ApiContext
    task_id: str
    api_key_id: str | None
    store: bool
    input_items: tuple[JSONDict, ...]
    response_event_sequence: int
    recorded_response_id: str
    storage_target: ResponseStorageTarget
    flush_interval_ms: int = DEFAULT_RESPONSES_PERSIST_FLUSH_INTERVAL_MS
    max_events_per_flush: int = DEFAULT_RESPONSES_PERSIST_MAX_EVENTS_PER_FLUSH
    max_pending_events: int = DEFAULT_RESPONSES_PERSIST_MAX_PENDING_EVENTS
    _pending_event_payloads: list[JSONDict] = field(default_factory=list[JSONDict])
    _pending_sequence_start: int | None = None
    _pending_response_json: JSONDict | None = None
    _pending_status: str = "in_progress"
    _last_flush_monotonic_ms: int = field(default_factory=monotonic_ms)
    _first_flush: bool = True

    def __post_init__(self) -> None:
        config = self.api_context.dependencies.config
        interval_candidate = int(
            config.get_int("SERVER.HTTP.STREAMING.RESPONSES_PERSIST_FLUSH_INTERVAL_MS"),
        )
        max_events_candidate = int(
            config.get_int("SERVER.HTTP.STREAMING.RESPONSES_PERSIST_MAX_EVENTS_PER_FLUSH"),
        )
        max_pending_candidate = int(
            config.get_int("SERVER.HTTP.STREAMING.RESPONSES_PERSIST_MAX_PENDING_EVENTS"),
        )
        self.flush_interval_ms = (
            int(interval_candidate)
            if interval_candidate > 0
            else DEFAULT_RESPONSES_PERSIST_FLUSH_INTERVAL_MS
        )
        self.max_events_per_flush = (
            int(max_events_candidate)
            if max_events_candidate > 0
            else DEFAULT_RESPONSES_PERSIST_MAX_EVENTS_PER_FLUSH
        )
        self.max_pending_events = (
            int(max_pending_candidate)
            if max_pending_candidate > 0
            else DEFAULT_RESPONSES_PERSIST_MAX_PENDING_EVENTS
        )

    async def emit_failure(self, *, code: str, message: str) -> bytes:
        if self.store:
            await self.flush_if_needed(force=True)
            failed_event = build_failed_response_event(
                response_id=self.recorded_response_id,
                message=message,
                code=code,
                model=self.storage_target.model,
                created_at=int(self.storage_target.created_at),
            )
            event_bytes, _terminal = self.emit_response_event(
                payload=failed_event,
                default_status="failed",
            )
            await self.flush_if_needed(force=True)
            return event_bytes
        return build_failed_event_bytes(
            response_id=self.recorded_response_id,
            message=message,
            code=code,
            model=self.storage_target.model,
            created_at=ms_to_seconds_floor(epoch_ms()),
        )

    def emit_response_event(
        self,
        *,
        payload: JSONDict,
        default_status: str = "in_progress",
    ) -> tuple[bytes, bool]:
        sequence = int(self.response_event_sequence)
        normalized_event = normalize_stored_response_event(
            target=self.storage_target,
            payload=dict(payload),
            sequence_number=sequence,
            default_status=default_status,
        )
        if self.store:
            self._buffer_stored_event(sequence=sequence, event=normalized_event)
        else:
            self._apply_storage_target(event=normalized_event)
        self.response_event_sequence += 1
        return (
            format_openai_sse_data(normalized_event.event_payload).encode("utf-8"),
            bool(normalized_event.terminal),
        )

    def _apply_storage_target(self, *, event: StoredResponseEvent) -> None:
        self.recorded_response_id = event.response_id
        self.storage_target = ResponseStorageTarget(
            response_id=event.response_id,
            task_id=self.task_id,
            user_id=self.storage_target.user_id,
            api_key_id=self.api_key_id,
            model=event.model,
            created_at=event.created_at,
            is_background=False,
            stream_enabled=True,
        )

    def _buffer_stored_event(self, *, sequence: int, event: StoredResponseEvent) -> None:
        self._apply_storage_target(event=event)
        if self._pending_sequence_start is None:
            self._pending_sequence_start = int(sequence)
        self._pending_event_payloads.append(dict(event.event_payload))
        self._pending_response_json = dict(event.response_json)
        self._pending_status = event.status or "in_progress"

    def _should_flush(self, *, now_monotonic_ms: int, force: bool) -> bool:
        if not self._pending_event_payloads:
            return False
        if force:
            return True
        pending_count = len(self._pending_event_payloads)
        if pending_count >= int(self.max_pending_events):
            return True
        if pending_count >= int(self.max_events_per_flush):
            return True
        elapsed = max(0, int(now_monotonic_ms) - int(self._last_flush_monotonic_ms))
        if elapsed >= int(self.flush_interval_ms):
            return True
        return False

    async def flush_if_needed(self, *, force: bool) -> None:
        if not self.store:
            return
        now_monotonic = int(monotonic_ms())
        if not self._should_flush(now_monotonic_ms=now_monotonic, force=force):
            return
        await self._flush_pending(now_monotonic_ms=now_monotonic)

    async def _flush_pending(self, *, now_monotonic_ms: int) -> None:
        if not self._pending_event_payloads:
            return
        if self._pending_sequence_start is None:
            raise ValidationError(
                "Response persistence invariant violated: sequence_start missing.",
            )
        sequence_start = int(self._pending_sequence_start)
        response_json = self._pending_response_json
        if response_json is None:
            raise ValidationError("Response persistence invariant violated: response_json missing.")
        for offset, payload in enumerate(self._pending_event_payloads):
            sequence_value = payload.get("sequence_number")
            expected_sequence = sequence_start + int(offset)
            if not is_strict_int(sequence_value):
                raise ValidationError(
                    "Response persistence invariant violated: event payload missing sequence_number.",
                )
            if int(sequence_value) != int(expected_sequence):
                raise ValidationError("Response persistence invariant violated: sequence mismatch.")
        now_epoch_ms = int(epoch_ms())
        persisted = (
            await self.api_context.dependencies.database_openai_responses.upsert_response_artifacts(
                response_id=self.recorded_response_id,
                task_id=self.task_id,
                user_id=self.storage_target.user_id,
                api_key_id=self.api_key_id,
                model=self.storage_target.model,
                created_at_seconds=int(self.storage_target.created_at),
                status=self._pending_status or "in_progress",
                store=True,
                is_background=False,
                stream_enabled=True,
                response_json=dict(response_json),
                input_items=self.input_items if self._first_flush else None,
                input_items_created_at_ms=now_epoch_ms,
                event_payloads=tuple(self._pending_event_payloads),
                event_sequence_start=int(sequence_start),
                reset_events=bool(self._first_flush),
                create_if_missing=bool(self._first_flush),
                event_created_at_ms=now_epoch_ms,
            )
        )
        if not persisted:
            self.store = False
        self.api_context.dependencies.metrics_manager.increment_counter(
            "api",
            "openai",
            "responses_stream",
            "persist_flushes_total",
        )
        self.api_context.dependencies.metrics_manager.increment_counter(
            "api",
            "openai",
            "responses_stream",
            "persist_events_total",
            value=len(self._pending_event_payloads),
        )
        self._pending_event_payloads.clear()
        self._pending_sequence_start = None
        self._pending_response_json = None
        self._pending_status = "in_progress"
        self._last_flush_monotonic_ms = int(now_monotonic_ms)
        self._first_flush = False

    @property
    def has_pending_events(self) -> bool:
        return bool(self._pending_event_payloads)
