"""SoAI - Structured subagent parent tool call update models [backend/features/agent/subagents/parent_tool_call_update_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.assistant_timeline.tool_result_truncation import (
    TIMELINE_TOOL_RESULT_OUTPUT_INLINE_MAX_CHARS,
)
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.execution.protocols import SubagentSnapshot
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ChildToolCallState",
    "TextBlockState",
    "build_live_subagent_record",
    "build_subagent_parent_tool_result",
    "normalize_result_with_output_delta",
    "order_child_tool_call_payloads",
)


def _append_capped_output(existing_output: str, delta: str) -> str:
    if not delta:
        return existing_output
    next_output = f"{existing_output}{delta}"
    if len(next_output) <= TIMELINE_TOOL_RESULT_OUTPUT_INLINE_MAX_CHARS:
        return next_output
    return next_output[len(next_output) - TIMELINE_TOOL_RESULT_OUTPUT_INLINE_MAX_CHARS :]


def normalize_result_with_output_delta(
    existing_result: JSONValue | None,
    output_delta: str,
) -> JSONValue:
    if not output_delta:
        return existing_result if existing_result is not None else {"output": ""}
    if isinstance(existing_result, dict):
        existing_output = existing_result.get("output")
        next_result = dict(existing_result)
        next_result["output"] = _append_capped_output(
            existing_output if isinstance(existing_output, str) else "",
            output_delta,
        )
        return next_result
    normalized_result: JSONDict = {}
    if existing_result is not None:
        normalized_result["value"] = existing_result
    normalized_result["output"] = _append_capped_output("", output_delta)
    return normalized_result


@dataclass(slots=True)
class TextBlockState:
    text: str
    started_at_ms: int
    block_index: int
    stream_order: int

    def to_json_dict(self) -> JSONDict:
        return {
            "text": self.text,
            "started_at_ms": self.started_at_ms,
            "block_index": self.block_index,
            "stream_order": self.stream_order,
        }


def build_subagent_parent_tool_result(
    *,
    subagent_record: JSONDict | None,
    child_tool_calls: list[JSONDict],
    text_blocks: list[TextBlockState],
) -> JSONDict:
    if subagent_record is None:
        raise ValidationError("Structured subagent parent tool result requires subagent.")
    payload: JSONDict = {
        "subagent": subagent_record,
        "subagent_stream": {
            "tool_calls": child_tool_calls,
            "text_blocks": [block.to_json_dict() for block in text_blocks],
        },
    }
    return payload


def build_live_subagent_record(
    *,
    snapshot: SubagentSnapshot,
    result_text: str | None,
    token_usage: JSONDict | None,
) -> JSONDict:
    return {
        "subagent_id": snapshot.subagent_id,
        "execution_type": snapshot.execution_type,
        "owner_task_id": snapshot.owner_task_id,
        "status": snapshot.status,
        "status_message": snapshot.status_message,
        "mode": snapshot.mode,
        "display_name": snapshot.display_name,
        "conv_id": snapshot.conv_id,
        "parent_turn_id": snapshot.parent_turn_id,
        "parent_tool_call_id": snapshot.parent_tool_call_id,
        "parent_iteration_index": snapshot.parent_iteration_index,
        "started_at_ms": snapshot.started_at_ms,
        "updated_at_ms": snapshot.updated_at_ms,
        "finished_at_ms": snapshot.finished_at_ms,
        "requested_model": snapshot.requested_model,
        "result_text": result_text,
        "error_message": snapshot.error_message,
        "error_type": snapshot.error_type,
        "token_usage": token_usage,
    }


@dataclass(slots=True)
class ChildToolCallState:
    call_id: str
    tool_name: str
    order_index: int
    stream_order: int
    content_index_before: int
    sequence_index: int | None = None
    started_at_ms: int | None = None
    duration_ms: int | None = None
    status: str = "pending"
    arguments: JSONValue | None = None
    result: JSONValue | None = None
    error: str | None = None
    code_diffs: list[JSONDict] | None = None

    def to_json_dict(self) -> JSONDict:
        stream_order, started_at_ms, sequence_index, _, _ = _resolve_child_tool_call_ordering_key(
            self,
        )
        payload: JSONDict = {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "status": self.status,
            "sequence_index": sequence_index,
            "started_at_ms": started_at_ms,
            "stream_order": stream_order,
            "content_index_before": self.content_index_before,
        }
        if self.duration_ms is not None:
            payload["duration_ms"] = self.duration_ms
        if self.arguments is not None:
            payload["arguments"] = self.arguments
        if self.result is not None:
            payload["result"] = self.result
        if self.code_diffs is not None:
            payload["code_diffs"] = [dict(entry) for entry in self.code_diffs]
        if isinstance(self.error, str) and self.error.strip():
            payload["error"] = self.error.strip()
        return payload


def _resolve_child_tool_call_ordering_key(
    item: ChildToolCallState,
) -> tuple[int, int, int, int, str]:
    if not is_strict_int(item.stream_order) or item.stream_order < 0:
        raise ValidationError("Subagent child tool call stream_order is required.")
    if not is_strict_int(item.started_at_ms) or item.started_at_ms < 0:
        raise ValidationError("Subagent child tool call started_at_ms is required.")
    if not is_strict_int(item.sequence_index) or item.sequence_index < 0:
        raise ValidationError("Subagent child tool call sequence_index is required.")
    if not is_strict_int(item.content_index_before) or item.content_index_before < 0:
        raise ValidationError("Subagent child tool call content_index_before is required.")
    return (
        item.stream_order,
        item.started_at_ms,
        item.sequence_index,
        item.order_index,
        item.call_id,
    )


def order_child_tool_call_payloads(child_tool_calls: list[ChildToolCallState]) -> list[JSONDict]:
    ordered = sorted(
        child_tool_calls,
        key=_resolve_child_tool_call_ordering_key,
    )
    return [item.to_json_dict() for item in ordered]
