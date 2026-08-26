"""SoAI - OpenAI stream tool-call chronology state [backend/core/openai/stream_transcript/tool_call_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import TYPE_CHECKING

from core.openai.stream_transcript.tool_call_contract_state import (
    OpenAIStreamToolCallContractState,
)
from core.openai.tool_call_assembly import (
    accumulate_tool_call,
    finalize_tool_calls_sorted,
)
from core.openai.tool_call_stream_matching import resolve_tool_call_key
from core.tool_calls.chronology import bound_optional_chronology_anchor
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("OpenAIStreamToolCallState",)


class OpenAIStreamToolCallState:
    def __init__(
        self,
        *,
        flush_text_boundary: Callable[[], None],
        get_content_index_before: Callable[[], int],
        get_thinking_index_before: Callable[[], int],
        get_thinking_duration_before_ms: Callable[[], int],
    ) -> None:
        self._flush_text_boundary = flush_text_boundary
        self._get_content_index_before = get_content_index_before
        self._get_thinking_index_before = get_thinking_index_before
        self._get_thinking_duration_before_ms = get_thinking_duration_before_ms
        self._tool_calls: dict[Hashable, JSONDict] = {}
        self._sequence_order: list[Hashable] = []
        self._sequence_hint_by_key: dict[Hashable, int] = {}
        self._stream_index_by_call_id: dict[str, int] = {}
        self._call_id_by_stream_index: dict[int, str] = {}
        self._next_sequence_index = 0
        self._emitted_tool_call_ids: set[str] = set()
        self._emitted_sequence_index_by_call_id: dict[str, int] = {}
        self._last_tool_payload_content_boundary: int | None = None
        self._last_tool_payload_thinking_boundary: int | None = None
        self._contract_state = OpenAIStreamToolCallContractState()

    def _sort_hint_value(self, hint: int | None) -> int:
        if hint is None:
            return 2_000_000_000
        return int(hint)

    def _insert_sequence_key(self, key: Hashable, hint: int | None) -> None:
        if hint is not None:
            self._sequence_hint_by_key[key] = int(hint)
        if key in self._sequence_order:
            return
        if hint is None:
            self._sequence_order.append(key)
            return
        insert_index = len(self._sequence_order)
        new_hint_value = self._sort_hint_value(hint)
        for index, existing_key in enumerate(self._sequence_order):
            existing_hint = self._sequence_hint_by_key.get(existing_key)
            if self._sort_hint_value(existing_hint) > new_hint_value:
                insert_index = index
                break
        self._sequence_order.insert(insert_index, key)

    def _reorder_sequence_key_if_needed(self, key: Hashable, hint: int) -> None:
        if key not in self._sequence_order:
            self._insert_sequence_key(key, hint)
            return
        existing_hint = self._sequence_hint_by_key.get(key)
        if existing_hint == hint:
            return
        self._sequence_hint_by_key[key] = int(hint)
        self._sequence_order.remove(key)
        self._insert_sequence_key(key, hint)

    def _renumber_sequence_indices(self) -> None:
        renumbered: list[Hashable] = []
        reserved_sequence_indexes = set(self._emitted_sequence_index_by_call_id.values())
        next_available_sequence_index = 0
        for key in self._sequence_order:
            entry = self._tool_calls.get(key)
            if entry is None:
                continue
            call_id_value = entry.get("id")
            call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
            emitted_sequence_index = self._emitted_sequence_index_by_call_id.get(call_id)
            if emitted_sequence_index is not None:
                entry["_sequence_index"] = emitted_sequence_index
            else:
                while next_available_sequence_index in reserved_sequence_indexes:
                    next_available_sequence_index += 1
                entry["_sequence_index"] = next_available_sequence_index
                next_available_sequence_index += 1
            renumbered.append(key)
        self._sequence_order = renumbered

    def consume_tool_calls_payload(self, source: JSONDict) -> None:
        calls = source.get("tool_calls")
        if not isinstance(calls, list):
            return
        self._flush_text_boundary()
        consumed_tool_call = False
        for call in calls:
            if not isinstance(call, dict):
                continue
            if resolve_tool_call_key(call) is None:
                continue
            call_id = call.get("id")
            call_index = coerce_optional_non_negative_int_strict(call.get("index"))
            if not isinstance(call_id, str) or not call_id:
                if call_index is not None:
                    indexed_call_id = self._call_id_by_stream_index.get(call_index)
                    if indexed_call_id is not None:
                        call["id"] = indexed_call_id
                        call_id = indexed_call_id
            if isinstance(call_id, str) and call_id and call_index is not None:
                existing_stream_index = self._stream_index_by_call_id.get(call_id)
                if existing_stream_index is None:
                    self._stream_index_by_call_id[call_id] = int(call_index)
                if call_index not in self._call_id_by_stream_index:
                    self._call_id_by_stream_index[call_index] = call_id
            key: Hashable | None = None
            if isinstance(call_id, str) and call_id and call_id in self._tool_calls:
                key = call_id
            elif isinstance(call_id, str) and call_id and call_index is not None:
                indexed_entry = self._tool_calls.get(call_index)
                indexed_entry_id = (
                    indexed_entry.get("id") if isinstance(indexed_entry, dict) else None
                )
                if indexed_entry is not None and (
                    not isinstance(indexed_entry_id, str)
                    or not indexed_entry_id
                    or indexed_entry_id == call_id
                ):
                    key = call_index
                else:
                    key = call_id
            elif call_index is not None and call_index in self._tool_calls:
                key = call_index
            elif isinstance(call_id, str) and call_id:
                key = call_id
            elif call_index is not None:
                key = call_index
            if key is None:
                continue
            known = key in self._tool_calls
            is_new = not known
            function_payload = call.get("function")
            arguments_fragment_value: str | None = None
            if isinstance(function_payload, dict):
                arguments_value = function_payload.get("arguments")
                arguments_fragment_value = (
                    arguments_value if isinstance(arguments_value, str) else None
                )
            existing_entry = self._tool_calls.get(key)
            existing_arguments = None
            if isinstance(existing_entry, dict):
                existing_function = existing_entry.get("function")
                if isinstance(existing_function, dict):
                    existing_arguments_value = existing_function.get("arguments")
                    if isinstance(existing_arguments_value, str):
                        existing_arguments = existing_arguments_value
            self._contract_state.observe(
                call_index=call_index,
                call_id=call_id if isinstance(call_id, str) and call_id else None,
                existing_arguments=existing_arguments if known else None,
                arguments_fragment=arguments_fragment_value,
                call_started=(
                    isinstance(function_payload, dict)
                    or isinstance(call.get("id"), str)
                    or isinstance(call.get("type"), str)
                ),
            )
            sort_hint = coerce_optional_non_negative_int_strict(call.get("sequence_index"))
            sequence_index_for_assembly = self._next_sequence_index if is_new else None
            if is_new:
                self._next_sequence_index += 1
            explicit_thinking_duration_before_ms = coerce_optional_non_negative_int_strict(
                call.get("thinking_duration_before_ms"),
            )
            thinking_duration_before_ms = 0
            if is_new:
                if explicit_thinking_duration_before_ms is not None:
                    thinking_duration_before_ms = explicit_thinking_duration_before_ms
                else:
                    thinking_duration_before_ms = self._get_thinking_duration_before_ms()
            explicit_content_index_before = coerce_optional_non_negative_int_strict(
                call.get("content_index_before"),
            )
            explicit_thinking_index_before = coerce_optional_non_negative_int_strict(
                call.get("thinking_index_before"),
            )
            content_index_boundary = self._get_content_index_before()
            thinking_index_boundary = self._get_thinking_index_before()
            if explicit_content_index_before is not None:
                content_index_before = bound_optional_chronology_anchor(
                    explicit_content_index_before,
                    "content_index_before",
                    upper_bound=content_index_boundary,
                )
            else:
                content_index_before = content_index_boundary
            if explicit_thinking_index_before is not None:
                thinking_index_before = bound_optional_chronology_anchor(
                    explicit_thinking_index_before,
                    "thinking_index_before",
                    upper_bound=thinking_index_boundary,
                )
            else:
                thinking_index_before = thinking_index_boundary
            accumulate_tool_call(
                self._tool_calls,
                call,
                sequence_index=sequence_index_for_assembly,
                thinking_duration_before_ms=thinking_duration_before_ms if is_new else None,
                content_index_before=content_index_before,
                thinking_index_before=thinking_index_before,
                explicit_content_index_before=explicit_content_index_before is not None,
                explicit_thinking_index_before=explicit_thinking_index_before is not None,
            )
            consumed_tool_call = True
            if known and isinstance(call_id, str) and call_id and call_index is not None:
                if call_id in self._sequence_order:
                    key = call_id
                elif call_index in self._sequence_order:
                    position = self._sequence_order.index(call_index)
                    self._sequence_order[position] = call_id
                    existing_hint = self._sequence_hint_by_key.pop(call_index, None)
                    if existing_hint is not None:
                        self._sequence_hint_by_key[call_id] = existing_hint
                    key = call_id
            if sort_hint is not None:
                self._reorder_sequence_key_if_needed(key, sort_hint)
            else:
                self._insert_sequence_key(key, None)
            self._renumber_sequence_indices()
        if consumed_tool_call:
            self._last_tool_payload_content_boundary = self._get_content_index_before()
            self._last_tool_payload_thinking_boundary = self._get_thinking_index_before()

    def get_tool_calls(self) -> list[JSONDict]:
        return finalize_tool_calls_sorted(self._tool_calls)

    def finalize_implicit_chronology(
        self,
        *,
        content_index_before: int,
        thinking_index_before: int,
    ) -> None:
        last_content_boundary = self._last_tool_payload_content_boundary
        last_thinking_boundary = self._last_tool_payload_thinking_boundary
        for entry in self._tool_calls.values():
            call_id_value = entry.get("id")
            call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
            if call_id in self._emitted_tool_call_ids:
                continue
            entry_content_index = coerce_optional_non_negative_int_strict(
                entry.get("_content_index_before"),
            )
            entry_thinking_index = coerce_optional_non_negative_int_strict(
                entry.get("_thinking_index_before"),
            )
            if (
                entry.get("_explicit_content_index_before") is not True
                and last_content_boundary is not None
                and content_index_before > last_content_boundary
                and entry_content_index == last_content_boundary
            ):
                entry["_content_index_before"] = content_index_before
            if (
                entry.get("_explicit_thinking_index_before") is not True
                and last_thinking_boundary is not None
                and thinking_index_before > last_thinking_boundary
                and entry_thinking_index == last_thinking_boundary
            ):
                entry["_thinking_index_before"] = thinking_index_before

    def drain_new_tool_calls(self) -> list[JSONDict]:
        new_calls: list[JSONDict] = []
        for tool_call in self.get_tool_calls():
            call_id_value = tool_call.get("id")
            call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
            function_value = tool_call.get("function")
            if not isinstance(function_value, dict):
                continue
            function_name_value = function_value.get("name")
            function_name = (
                function_name_value.strip() if isinstance(function_name_value, str) else ""
            )
            if not call_id or not function_name or call_id in self._emitted_tool_call_ids:
                continue
            self._emitted_tool_call_ids.add(call_id)
            sequence_index = coerce_optional_non_negative_int_strict(
                tool_call.get("sequence_index"),
            )
            if sequence_index is None:
                raise ValueError("Emitted tool call sequence_index must be a non-negative integer.")
            self._emitted_sequence_index_by_call_id[call_id] = sequence_index
            emitted_tool_call = dict(tool_call)
            emitted_tool_call["function"] = {"name": function_name}
            new_calls.append(emitted_tool_call)
        return new_calls

    def get_tool_call_contract_violation_summary(self) -> JSONDict | None:
        return self._contract_state.get_violation_summary()
