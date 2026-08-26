"""SoAI - Canonical prompt compaction projection [backend/database/repositories/users/prompt_compaction_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.tool_calls.context_compaction_markers import (
    CONTEXT_COMPACTION_TOOL_NAME,
    build_context_compaction_marker_from_tool_payload,
)
from core.tool_calls.status_values import is_terminal_tool_call_status
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int
from database.core.json_codec import safe_json_deserialize

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRow

__all__ = (
    "PromptCompactionProjection",
    "build_prompt_compaction_projections",
)


@dataclass(frozen=True, slots=True)
class PromptCompactionProjection:
    marker: JSONDict
    post_compaction_text: str


@dataclass(frozen=True, slots=True)
class _PromptCompactionCandidate:
    marker: JSONDict
    event_sequence: int
    tool_sequence_index: int


def _resolve_non_negative_int(value: JSONValue, *, source: str) -> int:
    if not is_strict_int(value) or value < 0:
        raise ValidationError(f"{source} must be a non-negative integer.")
    return int(value)


def _resolve_assistant_timestamp(value: JSONValue) -> int | None:
    if not is_strict_int(value):
        return None
    return int(value)


def _resolve_call_id(value: JSONValue) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _is_terminal_context_compaction_tool(tool_call: Mapping[str, JSONValue]) -> bool:
    tool_name_value = tool_call.get("tool_name")
    tool_name = tool_name_value.strip() if isinstance(tool_name_value, str) else ""
    if tool_name != CONTEXT_COMPACTION_TOOL_NAME:
        return False
    status_value = tool_call.get("status")
    status = status_value.strip() if isinstance(status_value, str) else ""
    return is_terminal_tool_call_status(status)


def _build_terminal_context_compaction_tools(
    tool_call_rows: Sequence[JSONDict],
) -> dict[tuple[int, str], JSONDict]:
    tools: dict[tuple[int, str], JSONDict] = {}
    for tool_call in tool_call_rows:
        if not _is_terminal_context_compaction_tool(tool_call):
            continue
        assistant_at_ms = _resolve_assistant_timestamp(tool_call.get("assistant_at_ms"))
        call_id = _resolve_call_id(tool_call.get("call_id"))
        if assistant_at_ms is None or not call_id:
            continue
        tools[(assistant_at_ms, call_id)] = dict(tool_call)
    return tools


def _decode_event_payload(event_row: SQLiteRow) -> JSONDict:
    payload = coerce_json_dict(
        normalize_for_json(safe_json_deserialize(event_row.get("payload_json"), None)),
    )
    if payload is None:
        raise ValidationError("Prompt compaction event payload_json must decode to an object.")
    return payload


def _resolve_event_identity(event_row: SQLiteRow) -> tuple[int, int, str]:
    assistant_at_ms = _resolve_non_negative_int(
        event_row.get("assistant_at_ms"),
        source="Prompt compaction event assistant_at_ms",
    )
    sequence = _resolve_non_negative_int(
        event_row.get("sequence"),
        source="Prompt compaction event sequence",
    )
    event_type_value = event_row.get("event_type")
    event_type = event_type_value.strip() if isinstance(event_type_value, str) else ""
    if not event_type:
        raise ValidationError("Prompt compaction event type must be a non-empty string.")
    return assistant_at_ms, sequence, event_type


def _build_candidate(
    *,
    tool_call: JSONDict,
    event_sequence: int,
) -> _PromptCompactionCandidate | None:
    marker = build_context_compaction_marker_from_tool_payload(tool_call)
    if marker is None:
        return None
    sequence_index = _resolve_non_negative_int(
        tool_call.get("sequence_index"),
        source="Prompt compaction tool sequence_index",
    )
    marker["sequence_index"] = sequence_index
    return _PromptCompactionCandidate(
        marker=marker,
        event_sequence=int(event_sequence),
        tool_sequence_index=sequence_index,
    )


def _collect_compaction_candidates(
    *,
    compaction_tools: Mapping[tuple[int, str], JSONDict],
    assistant_event_rows: Sequence[SQLiteRow],
) -> dict[int, _PromptCompactionCandidate]:
    candidates_by_timestamp: dict[int, _PromptCompactionCandidate] = {}
    for event_row in assistant_event_rows:
        assistant_at_ms, sequence, event_type = _resolve_event_identity(event_row)
        if event_type != "tool_call_completed":
            continue
        payload = _decode_event_payload(event_row)
        tool_payload = coerce_json_dict(payload.get("tool"))
        if tool_payload is None:
            raise ValidationError("Prompt compaction completed event requires a tool payload.")
        call_id = _resolve_call_id(tool_payload.get("call_id"))
        if not call_id:
            raise ValidationError("Prompt compaction completed event requires a call_id.")
        tool_call = compaction_tools.get((assistant_at_ms, call_id))
        if tool_call is None:
            continue
        candidate = _build_candidate(tool_call=tool_call, event_sequence=sequence)
        if candidate is None:
            continue
        existing = candidates_by_timestamp.get(assistant_at_ms)
        if existing is None or candidate.tool_sequence_index >= existing.tool_sequence_index:
            candidates_by_timestamp[assistant_at_ms] = candidate
    return candidates_by_timestamp


def _collect_post_compaction_text(
    *,
    candidates_by_timestamp: Mapping[int, _PromptCompactionCandidate],
    assistant_event_rows: Sequence[SQLiteRow],
) -> dict[int, str]:
    chunks_by_timestamp: dict[int, list[str]] = {}
    for event_row in assistant_event_rows:
        assistant_at_ms, sequence, event_type = _resolve_event_identity(event_row)
        candidate = candidates_by_timestamp.get(assistant_at_ms)
        if candidate is None:
            continue
        if event_type != "assistant_text_delta" or sequence <= candidate.event_sequence:
            continue
        payload = _decode_event_payload(event_row)
        delta_value = payload.get("delta")
        if not isinstance(delta_value, str):
            continue
        chunks = chunks_by_timestamp.get(assistant_at_ms)
        if chunks is None:
            chunks_by_timestamp[assistant_at_ms] = [delta_value]
        else:
            chunks.append(delta_value)
    return {
        assistant_at_ms: "".join(chunks) for assistant_at_ms, chunks in chunks_by_timestamp.items()
    }


def build_prompt_compaction_projections(
    *,
    tool_call_rows: Sequence[JSONDict],
    assistant_event_rows: Sequence[SQLiteRow],
) -> dict[int, PromptCompactionProjection]:
    compaction_tools = _build_terminal_context_compaction_tools(tool_call_rows)
    if not compaction_tools or not assistant_event_rows:
        return {}
    candidates_by_timestamp = _collect_compaction_candidates(
        compaction_tools=compaction_tools,
        assistant_event_rows=assistant_event_rows,
    )
    text_by_timestamp = _collect_post_compaction_text(
        candidates_by_timestamp=candidates_by_timestamp,
        assistant_event_rows=assistant_event_rows,
    )
    return {
        assistant_at_ms: PromptCompactionProjection(
            marker=dict(candidate.marker),
            post_compaction_text=text_by_timestamp.get(assistant_at_ms, ""),
        )
        for assistant_at_ms, candidate in candidates_by_timestamp.items()
    }
