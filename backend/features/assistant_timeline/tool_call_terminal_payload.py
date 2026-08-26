"""SoAI - Shared assistant timeline terminal tool-call payload building [backend/features/assistant_timeline/tool_call_terminal_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.file_content_previews import resolve_tool_activity_code_diffs
from core.tool_calls.status_values import (
    is_failure_tool_call_status,
    is_terminal_tool_call_status,
)
from core.tool_calls.tool_payloads import build_tool_payload
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.assistant_timeline.tool_event_layout import resolve_tool_call_identity

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "build_terminal_tool_payload",
    "resolve_pending_terminal_call_ids",
)


def resolve_pending_terminal_call_ids(runtime: AssistantTimelineRuntime) -> list[str]:
    pending_call_ids = (
        runtime.running_tool_call_ids
        | runtime.emitted_tool_call_ids
        | set(runtime.tool_call_layout_by_call_id.keys())
    )
    pending_tool_events = runtime.pending_tool_events
    if pending_tool_events is not None:
        for pending_event in pending_tool_events:
            pending_call_id_value = pending_event.tool_payload.get("call_id")
            if isinstance(pending_call_id_value, str) and pending_call_id_value.strip():
                pending_call_ids.add(pending_call_id_value.strip())
    return [
        call_id
        for call_id in pending_call_ids
        if call_id not in runtime.completed_tool_call_ids and call_id.strip()
    ]


def coerce_tool_result_payload(value: JSONValue) -> JSONValue | None:
    if isinstance(value, dict):
        result_payload: JSONDict = dict(value)
        return result_payload
    if isinstance(value, list):
        return list(value)
    return value


def merge_pending_output(
    result_payload: JSONValue | None,
    pending_output: str | None,
) -> JSONValue | None:
    if not pending_output:
        return result_payload
    if result_payload is None:
        return {"output": pending_output}
    if not isinstance(result_payload, dict):
        return {"value": result_payload, "output": pending_output}
    existing_output = result_payload.get("output")
    if isinstance(existing_output, str) and existing_output:
        return result_payload
    merged_payload: JSONDict = dict(result_payload)
    merged_payload["output"] = pending_output
    return merged_payload


def build_terminal_tool_payload(
    *,
    runtime: AssistantTimelineRuntime,
    call_id: str,
    layout_sequence_index: int,
    layout_content_index_before: int,
    layout_thinking_index_before: int,
    existing: JSONDict | None,
    default_status: str,
    default_error_message: str | None,
    default_tool_name: str,
    pending_output: str | None,
) -> JSONDict:
    resolved_status = default_status
    resolved_error_message = default_error_message
    resolved_tool_name = default_tool_name
    result_payload: JSONValue | None = None
    duration_ms: int | None = None
    thinking_duration_before_ms: int | None = None
    code_diffs: list[JSONDict] | None = None
    if existing is not None:
        existing_status = existing.get("status")
        existing_completed_at_ms = existing.get("completed_at_ms")
        if (
            isinstance(existing_status, str)
            and is_terminal_tool_call_status(existing_status)
            and existing_completed_at_ms is not None
        ):
            resolved_status = existing_status.strip().lower()
            existing_error = existing.get("error")
            resolved_error_message = (
                str(existing_error).strip()
                if is_failure_tool_call_status(resolved_status) and existing_error is not None
                else None
            )
        existing_tool_name = existing.get("tool_name")
        if isinstance(existing_tool_name, str) and existing_tool_name.strip():
            resolved_tool_name = existing_tool_name.strip()
        result_payload = coerce_tool_result_payload(existing.get("result"))
        duration_value = existing.get("duration_ms")
        if isinstance(duration_value, int) and duration_value >= 0:
            duration_ms = duration_value
        thinking_duration_value = existing.get("thinking_duration_before_ms")
        if isinstance(thinking_duration_value, int) and thinking_duration_value >= 0:
            thinking_duration_before_ms = thinking_duration_value
    if not resolved_tool_name:
        runtime_tool_name = runtime.tool_name_by_call_id.get(call_id)
        if isinstance(runtime_tool_name, str) and runtime_tool_name.strip():
            resolved_tool_name = runtime_tool_name.strip()
    if not resolved_tool_name:
        resolved_tool_name = "unknown_tool"
    result_payload = merge_pending_output(result_payload, pending_output)
    if result_payload is not None:
        code_diffs = resolve_tool_activity_code_diffs(resolved_tool_name, result_payload)
    runtime_identity = resolve_tool_call_identity(runtime, call_id)
    existing_message_index = existing.get("message_index") if isinstance(existing, dict) else None
    resolved_message_index = runtime.message_index
    if isinstance(existing_message_index, int) and existing_message_index >= 0:
        resolved_message_index = existing_message_index
    elif runtime_identity is not None:
        resolved_message_index = runtime_identity.message_index
    existing_turn_id = existing.get("turn_id") if isinstance(existing, dict) else None
    resolved_turn_id: str | None = None
    if isinstance(existing_turn_id, str) and existing_turn_id.strip():
        resolved_turn_id = existing_turn_id.strip()
    elif runtime_identity is not None and isinstance(runtime_identity.turn_id, str):
        if runtime_identity.turn_id.strip():
            resolved_turn_id = runtime_identity.turn_id.strip()
    elif isinstance(runtime.agent_turn_id, str) and runtime.agent_turn_id.strip():
        resolved_turn_id = runtime.agent_turn_id.strip()
    existing_iteration_index = (
        existing.get("iteration_index") if isinstance(existing, dict) else None
    )
    resolved_iteration_index: int | None = None
    if isinstance(existing_iteration_index, int) and existing_iteration_index >= 0:
        resolved_iteration_index = existing_iteration_index
    elif runtime_identity is not None and isinstance(runtime_identity.iteration_index, int):
        if runtime_identity.iteration_index >= 0:
            resolved_iteration_index = runtime_identity.iteration_index
    resolved_error = None
    if is_failure_tool_call_status(resolved_status):
        resolved_error = resolved_error_message or "Tool call did not complete."
    existing_assistant_turn_at_ms = coerce_optional_non_negative_int_strict(
        existing.get("assistant_turn_at_ms") if isinstance(existing, dict) else None,
    )
    existing_model_variant_index = coerce_optional_non_negative_int_strict(
        existing.get("model_variant_index") if isinstance(existing, dict) else None,
    )
    resolved_assistant_turn_at_ms = runtime.assistant_turn_at_ms
    resolved_model_variant_index = runtime.model_variant_index
    if existing_assistant_turn_at_ms is not None and existing_model_variant_index is not None:
        resolved_assistant_turn_at_ms = existing_assistant_turn_at_ms
        resolved_model_variant_index = existing_model_variant_index
    elif runtime_identity is not None:
        resolved_assistant_turn_at_ms = runtime_identity.assistant_identity.assistant_turn_at_ms
        resolved_model_variant_index = runtime_identity.assistant_identity.model_variant_index
    return build_tool_payload(
        call_id=call_id,
        tool_name=resolved_tool_name,
        status=resolved_status,
        message_index=resolved_message_index,
        assistant_turn_at_ms=resolved_assistant_turn_at_ms,
        model_variant_index=resolved_model_variant_index,
        sequence_index=layout_sequence_index,
        content_index_before=layout_content_index_before,
        thinking_index_before=layout_thinking_index_before,
        collapsed=True,
        turn_id=resolved_turn_id,
        iteration_index=resolved_iteration_index,
        result=result_payload,
        error=resolved_error,
        duration_ms=duration_ms,
        thinking_duration_before_ms=thinking_duration_before_ms,
        code_diffs=code_diffs,
    )
