"""SoAI - Tool call live projection publishing [backend/core/tool_calls/live_update_publishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.assistant_timeline.tool_event_payload_contract import (
    build_tool_event_payload_preview,
)
from core.database.requests import RecordToolCallLiveEventRequest
from core.errors.exceptions import StateError
from core.events.types_system import ToolCallLiveUpdatedEvent
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.tool_calls.live_update_identity import ToolCallLiveUpdateIdentity
from core.tool_calls.tool_name_policy import tool_call_running_result_is_detail_hydrated
from core.validation.epoch import is_unix_epoch_ms
from core.validation.integers import is_non_negative_strict_int, is_strict_int

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("publish_tool_call_live_update",)


def _require_int_field(payload: JSONDict, field_name: str) -> int:
    value = payload.get(field_name)
    if not is_strict_int(value):
        raise StateError(f"Tool live projection field {field_name!r} is missing.")
    return value


def _require_positive_int_field(payload: JSONDict, field_name: str) -> int:
    value = _require_int_field(payload, field_name)
    if value <= 0:
        raise StateError(f"Tool live projection field {field_name!r} must be positive.")
    return value


def _require_non_negative_int_field(payload: JSONDict, field_name: str) -> int:
    value = _require_int_field(payload, field_name)
    if not is_non_negative_strict_int(value):
        raise StateError(f"Tool live projection field {field_name!r} must be non-negative.")
    return value


def _require_epoch_ms_field(payload: JSONDict, field_name: str) -> int:
    value = _require_int_field(payload, field_name)
    if not is_unix_epoch_ms(value, enforce_maximum=False):
        raise StateError(f"Tool live projection field {field_name!r} must be epoch milliseconds.")
    return value


def _build_preview_projection(projection: JSONDict) -> JSONDict:
    return build_tool_event_payload_preview(projection)


def _tool_projection_running_result_is_detail_hydrated(projection: JSONDict) -> bool:
    tool_name = projection.get("tool_name")
    if not isinstance(tool_name, str):
        return False
    return tool_call_running_result_is_detail_hydrated(tool_name)


def _build_live_event_tool_projection(
    projection: JSONDict,
    *,
    event_type: str,
    status: str,
) -> JSONDict:
    preview = _build_preview_projection(projection)
    if (
        event_type == "tool_call_updated"
        and status in {"pending", "running"}
        and _tool_projection_running_result_is_detail_hydrated(preview)
    ):
        preview.pop("result", None)
    return preview


def _build_live_event_journal_payload(
    *,
    assistant_at_ms: int,
    tool_payload: JSONDict,
    event_type: str,
    status: str,
) -> JSONDict:
    return {
        "assistant_at_ms": assistant_at_ms,
        "tool": _build_live_event_tool_projection(
            tool_payload,
            event_type=event_type,
            status=status,
        ),
    }


async def publish_tool_call_live_update(
    *,
    event_bus: EventBusProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    identity: ToolCallLiveUpdateIdentity,
    call_id: str,
    event_type: str,
    tool_payload: JSONDict,
    status: str,
    duration_ms: int | None,
    started_at_ms: int | None,
    tool_result: JSONValue | None,
    error_message: str | None = None,
    completed_at_ms: int | None = None,
) -> ToolCallLiveUpdatedEvent:
    created_at_ms = epoch_ms()
    journal_payload = _build_live_event_journal_payload(
        assistant_at_ms=identity.assistant_at_ms,
        tool_payload=tool_payload,
        event_type=event_type,
        status=status,
    )
    serialized_tool_result = (
        serialize_json_compact_stable_strict(tool_result) if tool_result is not None else None
    )
    projection = await database_tool_calls.record_tool_call_live_event(
        RecordToolCallLiveEventRequest(
            conv_id=identity.conv_id,
            assistant_turn_at_ms=identity.assistant_turn_at_ms,
            model_variant_index=identity.model_variant_index,
            assistant_at_ms=identity.assistant_at_ms,
            call_id=call_id,
            event_type=event_type,
            payload_json=serialize_json_compact_stable_strict(journal_payload),
            status=status,
            created_at_ms=created_at_ms,
            duration_ms=duration_ms,
            started_at_ms=started_at_ms,
            tool_result=serialized_tool_result,
            error_message=error_message,
            completed_at_ms=completed_at_ms,
        ),
    )
    live_sequence = _require_non_negative_int_field(projection, "live_sequence")
    live_revision = _require_positive_int_field(projection, "live_revision")
    last_live_event_at_ms = _require_epoch_ms_field(projection, "last_live_event_at_ms")
    event = ToolCallLiveUpdatedEvent(
        user_id=identity.user_id,
        conv_id=identity.conv_id,
        request_id=identity.request_id,
        assistant_at_ms=identity.assistant_at_ms,
        assistant_turn_at_ms=identity.assistant_turn_at_ms,
        model_variant_index=identity.model_variant_index,
        call_id=call_id,
        live_sequence=live_sequence,
        live_revision=live_revision,
        last_live_event_at_ms=last_live_event_at_ms,
        event_type=event_type,
        tool=_build_live_event_tool_projection(
            projection,
            event_type=event_type,
            status=status,
        ),
    )
    await event_bus.publish(event)
    return event
