"""SoAI - Shared assistant timeline terminal tool-call synthesis [backend/features/assistant_timeline/tool_call_terminal_event_synthesis.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.assistant_timeline.tool_event_payload_contract import (
    build_tool_event_payload_preview,
)
from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms
from core.tool_calls.owner_task_reconciliation import (
    ToolCallOwnerTaskTerminalReconciliation,
    reconcile_tool_call_owner_task_terminal_states,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_TERMINAL_STATUSES,
    is_active_tool_call_status,
    is_failure_tool_call_status,
    is_terminal_tool_call_status,
)
from features.assistant_timeline.assistant_text import (
    flush_pending_assistant_text_and_finalize_processing_locked,
)
from features.assistant_timeline.publish import (
    ensure_chat_stream_publish_lock,
    publish_chat_stream_event_locked,
)
from features.assistant_timeline.tool_call_terminal_payload import (
    build_terminal_tool_payload,
)
from features.assistant_timeline.tool_call_terminal_payload_inputs import (
    merge_latest_result_into_existing_tool,
    resolve_pending_terminal_tool_output,
)
from features.assistant_timeline.tool_call_terminal_persistence import (
    finalize_persisted_tool_call_if_unfinished,
    resolve_persisted_tool_call,
)
from features.assistant_timeline.tool_call_terminal_preservation import (
    should_preserve_active_owned_tool_call,
)
from features.assistant_timeline.tool_call_terminal_runtime_snapshot import (
    resolve_terminal_tool_call_runtime_snapshot,
)
from features.assistant_timeline.tool_completed_live_update import (
    publish_completed_tool_live_update_locked,
)
from features.assistant_timeline.tool_event_layout import (
    cache_pending_tool_call_layout_from_runtime_locked,
    cache_tool_call_layout_from_payload,
    resolve_tool_call_layout,
)
from features.assistant_timeline.tool_events_flushing import (
    flush_pending_tool_output_deltas_for_call_id_locked,
)
from features.assistant_timeline.tool_events_state import (
    discard_pending_tool_events_for_call_id_locked,
)
from features.assistant_timeline.tool_payload_state import resolve_latest_tool_payload
from features.assistant_timeline.visible_activity_event_emission import (
    normalize_tool_payload_content_anchor_locked,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("synthesize_terminal_tool_call_events",)


async def synthesize_terminal_tool_call_events(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseStreamingMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task_registry: TaskRegistryLifecycleView,
    status: str,
    message: str,
    preserve_active_owned_tool_calls: bool,
) -> None:
    normalized_status = status.strip().lower()
    if normalized_status not in TOOL_CALL_TERMINAL_STATUSES:
        raise ValidationError(
            "Terminal tool call synthesis status must be completed, cancelled, or error.",
        )
    normalized_message = message.strip() if message.strip() else "Tool call did not complete."
    lock = ensure_chat_stream_publish_lock(runtime)
    reconciliation_requests: list[ToolCallOwnerTaskTerminalReconciliation] = []
    async with lock:
        snapshot = resolve_terminal_tool_call_runtime_snapshot(runtime)
        if not snapshot.pending_call_ids:
            return
        flushed_content_boundary = (
            await flush_pending_assistant_text_and_finalize_processing_locked(
                runtime=runtime,
                event_bus=event_bus,
                database_messages=database_messages,
                status=TOOL_CALL_STATUS_COMPLETED,
            )
        )
        visible_content_boundary = (
            flushed_content_boundary
            if flushed_content_boundary is not None
            else runtime.assistant_visible_chars
        )
        for call_id in snapshot.pending_call_ids:
            if call_id in snapshot.pending_subagent_call_ids:
                continue
            cache_pending_tool_call_layout_from_runtime_locked(
                runtime=runtime,
                call_id=call_id,
                content_boundary=visible_content_boundary,
            )
            layout = resolve_tool_call_layout(runtime, call_id)
            if layout is None:
                continue
            existing = await resolve_persisted_tool_call(
                runtime=runtime,
                database_tool_calls=database_tool_calls,
                call_id=call_id,
            )
            if isinstance(existing, dict):
                existing_tool_name = existing.get("tool_name")
                existing_status = existing.get("status")
                existing_completed_at_ms = existing.get("completed_at_ms")
                if (
                    isinstance(existing_tool_name, str)
                    and existing_tool_name.strip() == "subagent_spawn"
                    and existing_completed_at_ms is None
                    and isinstance(existing_status, str)
                    and is_active_tool_call_status(existing_status)
                ):
                    continue
                if preserve_active_owned_tool_calls and should_preserve_active_owned_tool_call(
                    existing,
                ):
                    runtime.post_terminal_tool_call_ids.add(call_id)
                    continue
            resolved_status = normalized_status
            resolved_error_message = (
                normalized_message if is_failure_tool_call_status(normalized_status) else None
            )
            resolved_tool_name = ""
            if not (isinstance(existing, dict) and existing.get("completed_at_ms") is not None):
                persisted = await finalize_persisted_tool_call_if_unfinished(
                    runtime=runtime,
                    database_tool_calls=database_tool_calls,
                    call_id=call_id,
                    status=resolved_status,
                    error_message=(
                        resolved_error_message
                        if is_failure_tool_call_status(resolved_status)
                        else None
                    ),
                    completed_at_ms=epoch_ms(),
                )
                if isinstance(persisted, dict):
                    persisted_status = persisted.get("status")
                    persisted_error = persisted.get("error")
                    if isinstance(persisted_status, str) and is_terminal_tool_call_status(
                        persisted_status,
                    ):
                        resolved_status = persisted_status.strip().lower()
                        resolved_error_message = (
                            str(persisted_error).strip()
                            if is_failure_tool_call_status(resolved_status)
                            and persisted_error is not None
                            else resolved_error_message
                        )
                    existing = persisted
            pending_output = resolve_pending_terminal_tool_output(
                runtime.pending_tool_output_deltas_by_call_id.get(call_id),
            )
            if call_id in runtime.emitted_tool_call_started_ids:
                await flush_pending_tool_output_deltas_for_call_id_locked(
                    event_bus=event_bus,
                    runtime=runtime,
                    database_messages=database_messages,
                    database_tool_calls=database_tool_calls,
                    call_id=call_id,
                )
                pending_output = None
            latest_tool_payload = resolve_latest_tool_payload(runtime, call_id)
            existing_for_payload = merge_latest_result_into_existing_tool(
                existing=existing if isinstance(existing, dict) else None,
                latest_payload=latest_tool_payload,
            )
            tool_payload = build_terminal_tool_payload(
                runtime=runtime,
                call_id=call_id,
                layout_sequence_index=layout.sequence_index,
                layout_content_index_before=layout.content_index_before,
                layout_thinking_index_before=layout.thinking_index_before,
                existing=existing_for_payload,
                default_status=resolved_status,
                default_error_message=resolved_error_message,
                default_tool_name=resolved_tool_name,
                pending_output=pending_output,
            )
            reconciliation_requests.append(
                ToolCallOwnerTaskTerminalReconciliation(
                    tool_call=dict(
                        existing_for_payload if existing_for_payload is not None else tool_payload,
                    ),
                    terminal_status=resolved_status,
                    terminal_message=resolved_error_message,
                ),
            )
            normalize_tool_payload_content_anchor_locked(
                runtime=runtime,
                tool_payload=tool_payload,
                content_boundary=visible_content_boundary,
            )
            cache_tool_call_layout_from_payload(runtime, tool_payload)
            await publish_completed_tool_live_update_locked(
                event_bus=event_bus,
                database_tool_calls=database_tool_calls,
                runtime=runtime,
                call_id=call_id,
                tool_payload=tool_payload,
            )
            runtime.pending_tool_output_deltas_by_call_id.pop(call_id, None)
            if pending_output is not None:
                runtime.tool_output_by_call_id[call_id] = pending_output
            await publish_chat_stream_event_locked(
                event_bus,
                runtime,
                database_messages,
                event_type="tool_call_completed",
                payload={
                    "assistant_at_ms": runtime.assistant_at_ms,
                    "tool": build_tool_event_payload_preview(tool_payload),
                },
            )
            runtime.completed_tool_call_ids.add(call_id)
            runtime.running_tool_call_ids.discard(call_id)
            discard_pending_tool_events_for_call_id_locked(runtime=runtime, call_id=call_id)
    await reconcile_tool_call_owner_task_terminal_states(
        task_registry=task_registry,
        reconciliations=reconciliation_requests,
    )
