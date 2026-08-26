"""SoAI - Post-terminal assistant timeline tool live projection [backend/features/assistant_timeline/post_terminal_tool_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.status_values import TOOL_CALL_STATUS_RUNNING
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.assistant_timeline.tool_completed_live_update import (
    publish_completed_tool_live_update_locked,
)
from features.assistant_timeline.tool_event_layout import (
    cache_tool_call_layout_from_payload,
)
from features.assistant_timeline.tool_events_state import (
    record_tool_call_completed_locked,
    record_tool_call_started_locked,
)
from features.assistant_timeline.tool_live_update_publishing import (
    publish_tool_call_live_update_for_runtime,
)
from features.assistant_timeline.tool_payload_state import (
    record_latest_tool_payload_locked,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.tool_calls.tool_event_payloads import NormalizedToolCallEvent
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "handle_post_terminal_tool_event_locked",
    "runtime_requires_post_terminal_tool_projection",
)


def runtime_requires_post_terminal_tool_projection(runtime: AssistantTimelineRuntime) -> bool:
    if runtime.detach_event is None or not runtime.detach_event.is_set():
        return False
    return runtime.terminal_event_emitted or runtime.terminal_finalization_started


def _record_started_projection_locked(
    *,
    runtime: AssistantTimelineRuntime,
    call_id: str,
    started_at_ms: int | None,
) -> None:
    record_tool_call_started_locked(runtime=runtime, call_id=call_id)
    runtime.emitted_tool_call_ids.add(call_id)
    runtime.emitted_tool_call_started_ids.add(call_id)
    if started_at_ms is not None:
        runtime.tool_call_started_at_ms_by_call_id[call_id] = started_at_ms


def _record_completed_projection_locked(
    *,
    runtime: AssistantTimelineRuntime,
    call_id: str,
) -> None:
    record_tool_call_completed_locked(runtime=runtime, call_id=call_id)
    runtime.emitted_tool_call_ids.add(call_id)
    runtime.tool_call_started_at_ms_by_call_id.pop(call_id, None)
    runtime.pending_tool_output_deltas_by_call_id.pop(call_id, None)
    runtime.post_terminal_tool_call_ids.discard(call_id)


async def handle_post_terminal_tool_event_locked(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_tool_calls: DatabaseToolCallsProtocol,
    normalized_event: NormalizedToolCallEvent,
    tool_payload: JSONDict,
) -> bool:
    if not runtime_requires_post_terminal_tool_projection(runtime):
        return False
    call_id = normalized_event.call_id.strip()
    if not call_id:
        return True
    if normalized_event.event_type not in {"tool_call_started", "tool_call_completed"}:
        return True
    cache_tool_call_layout_from_payload(runtime, tool_payload)
    record_latest_tool_payload_locked(runtime, tool_payload)
    if normalized_event.event_type == "tool_call_started":
        started_at_ms = coerce_optional_non_negative_int_strict(normalized_event.started_at_ms)
        await publish_tool_call_live_update_for_runtime(
            event_bus=event_bus,
            database_tool_calls=database_tool_calls,
            runtime=runtime,
            call_id=call_id,
            event_type="tool_call_started",
            tool_payload=tool_payload,
            status=TOOL_CALL_STATUS_RUNNING,
            duration_ms=None,
            started_at_ms=started_at_ms,
            tool_result=None,
        )
        _record_started_projection_locked(
            runtime=runtime,
            call_id=call_id,
            started_at_ms=started_at_ms,
        )
        return True
    await publish_completed_tool_live_update_locked(
        event_bus=event_bus,
        runtime=runtime,
        database_tool_calls=database_tool_calls,
        call_id=call_id,
        tool_payload=tool_payload,
    )
    _record_completed_projection_locked(runtime=runtime, call_id=call_id)
    return True
