"""SoAI - Assistant timeline pending tool-event sequence rebasing [backend/features/assistant_timeline/pending_tool_event_sequence_rebasing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue
from features.assistant_timeline.models import AssistantTimelineRuntime, ToolCallLayout

__all__ = ("rebase_pending_tool_event_sequences_for_reservation_locked",)


def _normalize_call_id(value: JSONValue) -> str:
    return value.strip() if isinstance(value, str) else ""


def rebase_pending_tool_event_sequences_for_reservation_locked(
    *,
    runtime: AssistantTimelineRuntime,
    reserved_sequence_index: int,
) -> None:
    if isinstance(reserved_sequence_index, bool) or reserved_sequence_index < 0:
        raise ValidationError(
            "Assistant timeline pending-tool-event sequence rebasing requires a non-negative sequence_index.",
        )
    pending = runtime.pending_tool_events
    if not pending:
        return
    sequence_index_by_call_id: dict[str, int] = {}
    for pending_event in pending:
        if int(pending_event.sequence_index) < int(reserved_sequence_index):
            continue
        call_id = _normalize_call_id(pending_event.tool_payload.get("call_id"))
        if not call_id:
            raise ValidationError(
                "Assistant timeline pending-tool-event sequence rebasing requires tool payload call_id.",
            )
        payload_sequence_index = pending_event.tool_payload.get("sequence_index")
        if (
            isinstance(payload_sequence_index, bool)
            or not isinstance(payload_sequence_index, int)
            or int(payload_sequence_index) != int(pending_event.sequence_index)
        ):
            raise ValidationError(
                "Assistant timeline pending-tool-event sequence rebasing requires consistent sequence_index payload.",
            )
        if call_id in runtime.emitted_tool_call_ids:
            message = "".join(
                (
                    "Assistant timeline pending-tool-event sequence rebasing cannot rebase ",
                    f"an emitted tool call_id '{call_id}'.",
                ),
            )
            raise ValidationError(
                message,
            )
        pending_sequence_index = int(pending_event.sequence_index)
        existing_sequence_index = sequence_index_by_call_id.get(call_id)
        if existing_sequence_index is None:
            sequence_index_by_call_id[call_id] = pending_sequence_index
        elif int(existing_sequence_index) != int(pending_sequence_index):
            message = "".join(
                (
                    "Assistant timeline pending-tool-event sequence rebasing found inconsistent ",
                    f"pending sequence indexes for call_id '{call_id}'.",
                ),
            )
            raise ValidationError(
                message,
            )
    if not sequence_index_by_call_id:
        return
    for pending_event in pending:
        call_id = _normalize_call_id(pending_event.tool_payload.get("call_id"))
        if not call_id:
            continue
        sequence_index = sequence_index_by_call_id.get(call_id)
        if sequence_index is None:
            continue
        if int(pending_event.sequence_index) != int(sequence_index):
            message = "".join(
                (
                    "Assistant timeline pending-tool-event sequence rebasing found inconsistent ",
                    f"pending sequence indexes for call_id '{call_id}'.",
                ),
            )
            raise ValidationError(
                message,
            )
        rebased_sequence_index = int(sequence_index) + 1
        pending_event.sequence_index = rebased_sequence_index
        pending_event.tool_payload["sequence_index"] = rebased_sequence_index
    _rebase_cached_tool_call_layouts_and_ownership(
        runtime=runtime,
        reserved_sequence_index=reserved_sequence_index,
        affected_call_ids=set(sequence_index_by_call_id),
    )


def _rebase_cached_tool_call_layouts_and_ownership(
    *,
    runtime: AssistantTimelineRuntime,
    reserved_sequence_index: int,
    affected_call_ids: set[str],
) -> None:
    rebased_call_ids: list[str] = []
    old_sequence_index_by_call_id: dict[str, int] = {}
    existing_layout_by_call_id: dict[str, ToolCallLayout] = {}
    for call_id in sorted(affected_call_ids):
        existing_sequence_index = runtime.tool_call_sequence_index_by_call_id.get(call_id)
        existing_layout = runtime.tool_call_layout_by_call_id.get(call_id)
        if existing_sequence_index is None and existing_layout is None:
            continue
        if existing_sequence_index is None or existing_layout is None:
            message = "".join(
                (
                    "Assistant timeline pending-tool-event sequence rebasing found incomplete ",
                    f"cached layout ownership for call_id '{call_id}'.",
                ),
            )
            raise ValidationError(
                message,
            )
        if int(existing_sequence_index) < int(reserved_sequence_index):
            message = "".join(
                (
                    "Assistant timeline pending-tool-event sequence rebasing found inconsistent ",
                    f"cached ownership for call_id '{call_id}'.",
                ),
            )
            raise ValidationError(
                message,
            )
        rebased_call_ids.append(call_id)
        old_sequence_index_by_call_id[call_id] = int(existing_sequence_index)
        existing_layout_by_call_id[call_id] = existing_layout

    if not rebased_call_ids:
        return

    for call_id in rebased_call_ids:
        old_sequence_index = old_sequence_index_by_call_id[call_id]
        existing_owner = runtime.tool_call_call_id_by_sequence_index.get(old_sequence_index)
        if existing_owner is not None and existing_owner != call_id:
            message = "".join(
                (
                    "Assistant timeline pending-tool-event sequence rebasing found conflicting ",
                    f"cached ownership for sequence_index {old_sequence_index}.",
                ),
            )
            raise ValidationError(
                message,
            )
        runtime.tool_call_call_id_by_sequence_index.pop(old_sequence_index, None)
        runtime.tool_call_sequence_index_by_call_id.pop(call_id, None)

    for call_id in rebased_call_ids:
        old_sequence_index = old_sequence_index_by_call_id[call_id]
        new_sequence_index = int(old_sequence_index) + 1
        existing_layout = existing_layout_by_call_id[call_id]
        existing_owner = runtime.tool_call_call_id_by_sequence_index.get(new_sequence_index)
        if existing_owner is not None and existing_owner != call_id:
            message = "".join(
                (
                    "Assistant timeline pending-tool-event sequence rebasing cannot assign ",
                    f"sequence_index {new_sequence_index} to call_id '{call_id}' because it is ",
                    f"already owned by call_id '{existing_owner}'.",
                ),
            )
            raise ValidationError(
                message,
            )
        runtime.tool_call_call_id_by_sequence_index[new_sequence_index] = call_id
        runtime.tool_call_sequence_index_by_call_id[call_id] = new_sequence_index
        if int(existing_layout.sequence_index) != int(old_sequence_index):
            message = "".join(
                (
                    "Assistant timeline pending-tool-event sequence rebasing found inconsistent ",
                    f"cached layout for call_id '{call_id}'.",
                ),
            )
            raise ValidationError(
                message,
            )
        runtime.tool_call_layout_by_call_id[call_id] = ToolCallLayout(
            sequence_index=new_sequence_index,
            content_index_before=int(existing_layout.content_index_before),
            thinking_index_before=int(existing_layout.thinking_index_before),
            thinking_duration_before_ms=existing_layout.thinking_duration_before_ms,
        )
