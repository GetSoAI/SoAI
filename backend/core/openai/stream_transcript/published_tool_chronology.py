"""SoAI - Published streamed tool chronology ownership [backend/core/openai/stream_transcript/published_tool_chronology.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ModelOutputContractError
from core.tool_calls.chronology import (
    ToolCallChronologyFields,
    resolve_tool_call_chronology_fields,
)
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("PublishedToolCallChronology",)


class PublishedToolCallChronology:
    def __init__(self) -> None:
        self._by_call_id: dict[str, ToolCallChronologyFields] = {}

    def snapshot(self, call: JSONDict) -> None:
        call_id = call.get("id")
        if not isinstance(call_id, str) or not call_id:
            raise ModelOutputContractError("Published tool call has no stable id.")
        self._by_call_id[call_id] = resolve_tool_call_chronology_fields(call)

    def validate_fragment(self, call_id: str, fragment: JSONDict) -> None:
        snapshot = self._by_call_id.get(call_id)
        if snapshot is None:
            return
        for field_name, expected in (
            ("sequence_index", snapshot.sequence_index),
            ("content_index_before", snapshot.content_index_before),
            ("thinking_index_before", snapshot.thinking_index_before),
            ("thinking_duration_before_ms", snapshot.thinking_duration_before_ms),
        ):
            if field_name not in fragment:
                continue
            if (
                field_name == "thinking_duration_before_ms"
                and fragment[field_name] is None
                and expected is None
            ):
                continue
            supplied = coerce_optional_non_negative_int_strict(fragment.get(field_name))
            if supplied is None or supplied != expected:
                raise ModelOutputContractError(
                    "Streamed tool call changed published chronology.",
                    details={"field": field_name},
                )

    def apply(self, call: JSONDict) -> None:
        call_id = call.get("id")
        snapshot = self._by_call_id.get(call_id) if isinstance(call_id, str) else None
        if snapshot is None:
            return
        call["sequence_index"] = snapshot.sequence_index
        call["content_index_before"] = snapshot.content_index_before
        call["thinking_index_before"] = snapshot.thinking_index_before
        if snapshot.thinking_duration_before_ms is not None:
            call["thinking_duration_before_ms"] = snapshot.thinking_duration_before_ms
        else:
            call.pop("thinking_duration_before_ms", None)

    def reserved_sequence_indexes(self) -> set[int]:
        return {snapshot.sequence_index for snapshot in self._by_call_id.values()}

    def sequence_for(self, call_id: str) -> int | None:
        snapshot = self._by_call_id.get(call_id)
        return snapshot.sequence_index if snapshot is not None else None
