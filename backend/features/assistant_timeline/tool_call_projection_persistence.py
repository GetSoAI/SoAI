"""SoAI - Assistant timeline tool-call projection persistence [backend/features/assistant_timeline/tool_call_projection_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.requests import CreateToolCallRequest
from core.errors.exceptions import StateError
from core.openai.tool_call_arguments import normalize_openai_tool_call_arguments
from core.tool_calls.chronology import (
    resolve_optional_non_negative_integer,
    resolve_required_non_negative_integer,
)
from core.tool_calls.storage_identity import build_tool_call_storage_id_from_fields
from core.validation.strings import coerce_required_non_empty_str
from features.assistant_timeline.tool_event_layout import (
    resolve_tool_call_identity,
    resolve_tool_call_layout,
)

if TYPE_CHECKING:
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("persist_tool_call_created_projection",)


def _require_trimmed_string(payload: JSONDict, field_name: str) -> str:
    return coerce_required_non_empty_str(
        payload.get(field_name),
        label=f"Tool call projection field {field_name!r}",
    )


def _require_non_negative_integer(payload: JSONDict, field_name: str) -> int:
    return resolve_required_non_negative_integer(
        payload.get(field_name),
        field_name,
        field_label="Tool call projection",
        required_message=f"Tool call projection field {field_name!r} is required.",
    )


def _resolve_optional_non_negative_integer(payload: JSONDict, field_name: str) -> int | None:
    return resolve_optional_non_negative_integer(
        payload.get(field_name),
        field_name,
        field_label="Tool call projection",
    )


def _resolve_tool_arguments(payload: JSONDict) -> str | None:
    if "arguments" not in payload:
        return None
    raw_arguments: JSONValue = payload.get("arguments")
    _arguments_payload, arguments_json, _arguments_error = normalize_openai_tool_call_arguments(
        raw_arguments,
    )
    return arguments_json


def _require_payload_matches_timeline_layout(
    *,
    runtime: AssistantTimelineRuntime,
    call_id: str,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
) -> None:
    layout = resolve_tool_call_layout(runtime, call_id)
    if layout is None:
        raise StateError("Tool call projection missing assistant timeline layout.")
    if (
        layout.sequence_index != sequence_index
        or layout.content_index_before != content_index_before
        or layout.thinking_index_before != thinking_index_before
    ):
        raise StateError("Tool call projection chronology conflicts with timeline layout.")


async def persist_tool_call_created_projection(
    *,
    runtime: AssistantTimelineRuntime,
    database_tool_calls: DatabaseToolCallsProtocol,
    tool_payload: JSONDict,
) -> None:
    call_id = _require_trimmed_string(tool_payload, "call_id")
    tool_name = _require_trimmed_string(tool_payload, "tool_name")
    message_index = _require_non_negative_integer(tool_payload, "message_index")
    sequence_index = _require_non_negative_integer(tool_payload, "sequence_index")
    content_index_before = _require_non_negative_integer(
        tool_payload,
        "content_index_before",
    )
    thinking_index_before = _require_non_negative_integer(
        tool_payload,
        "thinking_index_before",
    )
    thinking_duration_before_ms = _resolve_optional_non_negative_integer(
        tool_payload,
        "thinking_duration_before_ms",
    )
    _require_payload_matches_timeline_layout(
        runtime=runtime,
        call_id=call_id,
        sequence_index=sequence_index,
        content_index_before=content_index_before,
        thinking_index_before=thinking_index_before,
    )
    identity = resolve_tool_call_identity(runtime, call_id)
    if identity is None:
        raise StateError("Tool call projection identity could not be resolved.")
    assistant_turn_at_ms = identity.assistant_identity.assistant_turn_at_ms
    model_variant_index = identity.assistant_identity.model_variant_index
    storage_call_id = build_tool_call_storage_id_from_fields(
        conv_id=runtime.conv_id,
        turn_id=identity.turn_id,
        iteration_index=identity.iteration_index,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
        message_index=message_index,
        call_id=call_id,
    )
    tool_arguments = _resolve_tool_arguments(tool_payload)
    await runtime.require_mutation_allowed()
    await database_tool_calls.create_tool_call(
        CreateToolCallRequest(
            call_id=call_id,
            storage_call_id=storage_call_id,
            conv_id=runtime.conv_id,
            turn_id=identity.turn_id,
            iteration_index=identity.iteration_index,
            message_index=message_index,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
            assistant_at_ms=identity.assistant_identity.assistant_at_ms,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            status="pending",
            sequence_index=sequence_index,
            content_index_before=content_index_before,
            thinking_index_before=thinking_index_before,
            thinking_duration_before_ms=thinking_duration_before_ms,
            collapsed=True,
            error_message=None,
            tool_result=None,
            duration_ms=0,
            created_at_ms=None,
            completed_at_ms=None,
        ),
    )
