"""SoAI - Tool-call payload builders [backend/core/tool_calls/tool_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.code_diffs import normalize_code_diffs_payload
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_tool_payload",)


def build_tool_payload(
    *,
    call_id: str,
    tool_name: str,
    status: str,
    message_index: int,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
    collapsed: bool,
    assistant_turn_at_ms: int | None = None,
    model_variant_index: int | None = None,
    turn_id: str | None = None,
    iteration_index: int | None = None,
    arguments: JSONValue | None = None,
    started_at_ms: int | None = None,
    result: JSONValue | None = None,
    error: str | None = None,
    duration_ms: int | None = None,
    thinking_duration_before_ms: int | None = None,
    code_diffs: list[JSONDict] | None = None,
) -> JSONDict:
    payload: JSONDict = {
        "call_id": call_id,
        "tool_name": tool_name,
        "status": status,
        "message_index": int(message_index),
        "sequence_index": int(sequence_index),
        "content_index_before": int(content_index_before),
        "thinking_index_before": int(thinking_index_before),
        "collapsed": bool(collapsed),
    }
    normalized_turn_id = coerce_optional_trimmed_str(turn_id)
    if normalized_turn_id is not None:
        payload["turn_id"] = normalized_turn_id
    if iteration_index is not None and iteration_index >= 0:
        payload["iteration_index"] = int(iteration_index)
    if assistant_turn_at_ms is not None and assistant_turn_at_ms >= 0:
        payload["assistant_turn_at_ms"] = int(assistant_turn_at_ms)
    if model_variant_index is not None and model_variant_index >= 0:
        payload["model_variant_index"] = int(model_variant_index)
    if arguments is not None:
        payload["arguments"] = arguments
    if started_at_ms is not None and started_at_ms >= 0:
        payload["started_at_ms"] = int(started_at_ms)
    if result is not None:
        payload["result"] = result
    normalized_error = coerce_optional_trimmed_str(error)
    if normalized_error is not None:
        payload["error"] = normalized_error
    if duration_ms is not None and duration_ms >= 0:
        payload["duration_ms"] = int(duration_ms)
    if thinking_duration_before_ms is not None and thinking_duration_before_ms >= 0:
        payload["thinking_duration_before_ms"] = int(thinking_duration_before_ms)
    normalized_code_diffs = normalize_code_diffs_payload(code_diffs)
    if normalized_code_diffs is not None:
        payload["code_diffs"] = normalized_code_diffs
    return payload
