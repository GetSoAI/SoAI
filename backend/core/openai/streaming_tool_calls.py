"""SoAI - Shared OpenAI streaming tool-call rewriting [backend/core/openai/streaming_tool_calls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from core.openai.sse_rewrite import rewrite_openai_sse_json_payload_frame
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.tool_calls.chronology import offset_required_chronology_anchor
from core.types.json import JSONDict, JSONValue
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

__all__ = (
    "inject_collected_tool_calls_into_payload",
    "rewrite_agentic_tool_call_chronology_in_frame",
    "rewrite_missing_tool_call_ids_in_sse_frame",
)


def inject_collected_tool_calls_into_payload(
    payload: JSONDict,
    tool_calls: list[JSONDict],
) -> None:
    choices_value = payload.get("choices")
    if not isinstance(choices_value, list) or not choices_value:
        return
    first_choice = choices_value[0]
    if not isinstance(first_choice, dict):
        return
    message_value = first_choice.get("message")
    if not isinstance(message_value, dict):
        return
    message_value["tool_calls"] = [dict(tool_call) for tool_call in tool_calls]


def _rewrite_tool_call_offsets(
    tool_calls_value: JSONValue,
    *,
    tool_sequence_offset: int,
    content_index_offset: int,
    thinking_index_offset: int,
) -> bool:
    if not isinstance(tool_calls_value, list) or not tool_calls_value:
        return False
    any_updated = False
    for tool_call in tool_calls_value:
        if not isinstance(tool_call, dict):
            continue
        index_value = coerce_optional_non_negative_int_strict(tool_call.get("index"))
        if index_value is not None and tool_sequence_offset:
            tool_call["index"] = index_value + tool_sequence_offset
            any_updated = True
        sequence_index_value = coerce_optional_non_negative_int_strict(
            tool_call.get("sequence_index"),
        )
        if sequence_index_value is not None and tool_sequence_offset:
            tool_call["sequence_index"] = sequence_index_value + tool_sequence_offset
            any_updated = True
        rewritten_index = coerce_optional_non_negative_int_strict(tool_call.get("index"))
        if rewritten_index is None:
            rewritten_index = coerce_optional_non_negative_int_strict(
                tool_call.get("sequence_index"),
            )
            if rewritten_index is not None:
                tool_call["index"] = rewritten_index
                any_updated = True
        content_index_before_value = coerce_optional_non_negative_int_strict(
            tool_call.get("content_index_before"),
        )
        if content_index_before_value is not None and content_index_offset:
            tool_call["content_index_before"] = offset_required_chronology_anchor(
                content_index_before_value,
                "content_index_before",
                offset=content_index_offset,
            )
            any_updated = True
        thinking_index_before_value = coerce_optional_non_negative_int_strict(
            tool_call.get("thinking_index_before"),
        )
        if thinking_index_before_value is not None and thinking_index_offset:
            tool_call["thinking_index_before"] = offset_required_chronology_anchor(
                thinking_index_before_value,
                "thinking_index_before",
                offset=thinking_index_offset,
            )
            any_updated = True
        call_id_value = tool_call.get("id")
        call_id = call_id_value.strip() if isinstance(call_id_value, str) and call_id_value else ""
        if not call_id and rewritten_index is not None:
            tool_call["id"] = f"call_{rewritten_index}"
            any_updated = True
    return any_updated


def _rewrite_tool_calls_in_choices(
    payload: JSONDict,
    callback: Callable[[JSONValue], bool],
) -> bool:
    changed = False
    choices_value = payload.get("choices")
    if not isinstance(choices_value, list):
        return False
    for choice_value in choices_value:
        if not isinstance(choice_value, dict):
            continue
        delta_value = choice_value.get("delta")
        if isinstance(delta_value, dict):
            changed = callback(delta_value.get("tool_calls")) or changed
        message_value = choice_value.get("message")
        if isinstance(message_value, dict):
            changed = callback(message_value.get("tool_calls")) or changed
    return changed


def rewrite_agentic_tool_call_chronology_in_frame(
    frame: bytes,
    *,
    tool_sequence_offset: int,
    content_index_offset: int,
    thinking_index_offset: int,
) -> bytes:
    def rewrite_payload(payload: JSONDict) -> bool:
        return _rewrite_tool_calls_in_choices(
            payload,
            lambda tool_calls: _rewrite_tool_call_offsets(
                tool_calls,
                tool_sequence_offset=tool_sequence_offset,
                content_index_offset=content_index_offset,
                thinking_index_offset=thinking_index_offset,
            ),
        )

    return rewrite_openai_sse_json_payload_frame(
        frame,
        rewrite_payload=rewrite_payload,
    )


def _ensure_tool_call_ids(
    tool_calls_value: JSONValue,
    *,
    tool_call_ids_by_index: dict[int, str],
    tool_call_ids_by_ordinal: dict[int, str],
) -> bool:
    if not isinstance(tool_calls_value, list) or not tool_calls_value:
        return False
    local_changed = False
    for ordinal, call_value in enumerate(tool_calls_value):
        if not isinstance(call_value, dict):
            continue
        existing_id = call_value.get("id")
        normalized_existing_id = existing_id.strip() if isinstance(existing_id, str) else ""
        index_value = call_value.get("index")
        index = index_value if is_strict_int(index_value) and index_value >= 0 else None
        if normalized_existing_id:
            if index is not None and index not in tool_call_ids_by_index:
                tool_call_ids_by_index[index] = normalized_existing_id
            if ordinal not in tool_call_ids_by_ordinal:
                tool_call_ids_by_ordinal[ordinal] = normalized_existing_id
            continue
        if index is not None:
            call_id = tool_call_ids_by_index.get(index)
            if call_id is None:
                call_id = create_prefixed_hex_id("call")
                tool_call_ids_by_index[index] = call_id
            if ordinal not in tool_call_ids_by_ordinal:
                tool_call_ids_by_ordinal[ordinal] = call_id
            call_value["id"] = call_id
            local_changed = True
            continue
        call_id = tool_call_ids_by_ordinal.get(ordinal)
        if call_id is None:
            call_id = create_prefixed_hex_id("call")
            tool_call_ids_by_ordinal[ordinal] = call_id
        call_value["id"] = call_id
        local_changed = True
    return local_changed


def rewrite_missing_tool_call_ids_in_sse_frame(
    frame_text: str,
    *,
    tool_call_ids_by_index: dict[int, str],
    tool_call_ids_by_ordinal: dict[int, str],
) -> str:
    if "tool_calls" not in frame_text:
        return frame_text
    original = frame_text.encode("utf-8")

    def rewrite_payload(payload: JSONDict) -> bool:
        return _rewrite_tool_calls_in_choices(
            payload,
            lambda tool_calls: _ensure_tool_call_ids(
                tool_calls,
                tool_call_ids_by_index=tool_call_ids_by_index,
                tool_call_ids_by_ordinal=tool_call_ids_by_ordinal,
            ),
        )

    rewritten = rewrite_openai_sse_json_payload_frame(
        original,
        rewrite_payload=rewrite_payload,
    )
    if rewritten == original:
        return frame_text
    return rewritten.decode("utf-8")
