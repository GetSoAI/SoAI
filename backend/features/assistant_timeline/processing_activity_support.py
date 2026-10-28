"""SoAI - Shared processing activity payload support [backend/features/assistant_timeline/processing_activity_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.activity_payloads import build_activity_payload
from core.timing.monotonic import monotonic_ms
from core.validation.integers import coerce_non_negative_int_or_zero
from features.assistant_timeline.activity_status_sets import TIMELINE_ACTIVITY_STATUS_RUNNING
from features.assistant_timeline.activity_timing import ensure_activity_start_times

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "PROCESSING_IDLE_THRESHOLD_MS",
    "build_processing_activity_payload",
    "can_start_timeline_activity",
    "ensure_processing_activity_start_times",
    "has_running_activity_before_processing",
    "note_visible_activity_locked",
)

PROCESSING_IDLE_THRESHOLD_MS: int = 8000


def can_start_timeline_activity(runtime: AssistantTimelineRuntime) -> bool:
    return (
        runtime.detach_event is not None
        and not runtime.detach_event.is_set()
        and not runtime.cancellation_requested
        and not runtime.terminal_finalization_started
        and not runtime.terminal_event_emitted
    )


def ensure_processing_activity_start_times(
    runtime: AssistantTimelineRuntime,
    *,
    now_epoch_ms: int,
    now_monotonic_ms: int,
) -> tuple[int, int]:
    return ensure_activity_start_times(
        runtime.processing_activity,
        default_started_at_epoch_ms=int(now_epoch_ms),
        default_started_at_monotonic_ms=int(now_monotonic_ms),
    )


def has_running_activity_before_processing(runtime: AssistantTimelineRuntime) -> bool:
    if runtime.loading_activity.status == "running":
        return True
    if runtime.wait_for_user_activity.status == TIMELINE_ACTIVITY_STATUS_RUNNING:
        return True
    if runtime.thinking_phases is not None and any(
        phase.get("status") == TIMELINE_ACTIVITY_STATUS_RUNNING for phase in runtime.thinking_phases
    ):
        return True
    if runtime.pending_tool_events:
        return True
    if runtime.pending_tool_output_deltas_by_call_id:
        return True
    emitted_tool_call_ids = runtime.emitted_tool_call_ids
    if emitted_tool_call_ids:
        started_tool_call_ids = runtime.started_tool_call_ids
        completed_tool_call_ids = runtime.completed_tool_call_ids
        for call_id in emitted_tool_call_ids:
            if call_id not in started_tool_call_ids and call_id not in completed_tool_call_ids:
                return True
    if runtime.running_tool_call_ids:
        return True
    return False


def build_processing_activity_payload(
    *,
    runtime: AssistantTimelineRuntime,
    status: str,
    duration_ms: int,
    now_epoch_ms: int,
    now_monotonic_ms: int,
    reason: str | None = None,
    error_type: str | None = None,
) -> JSONDict:
    started_at_epoch_ms, _started_at_monotonic_ms = ensure_processing_activity_start_times(
        runtime,
        now_epoch_ms=now_epoch_ms,
        now_monotonic_ms=now_monotonic_ms,
    )
    return build_activity_payload(
        status=status,
        started_at_ms=started_at_epoch_ms,
        duration_ms=duration_ms,
        reason=reason,
        error_type=error_type,
    )


def note_visible_activity_locked(
    runtime: AssistantTimelineRuntime,
    *,
    now_ms: int | None = None,
) -> int:
    resolved_now_ms = (
        coerce_non_negative_int_or_zero(now_ms) if now_ms is not None else monotonic_ms()
    )
    runtime.last_visible_activity_monotonic_ms = resolved_now_ms
    return resolved_now_ms
