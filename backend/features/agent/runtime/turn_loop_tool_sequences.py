"""SoAI - Agent turn-loop tool sequence resolution [backend/features/agent/runtime/turn_loop_tool_sequences.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.content_text_rendering import render_openai_content_text
from core.openai.text_tool_call_extraction import extract_text_tool_calls
from core.openai.tool_call_text_lengths import extract_assistant_payload_text_lengths
from core.openai.tool_calls import extract_tool_calls_from_payload
from core.tool_calls.chronology import offset_required_chronology_anchor
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.agent.runtime.tool_sequence_indexing import (
    apply_tool_sequence_offset,
    resolve_next_tool_sequence_index,
)
from features.agent.runtime.turn_loop_inference_success import (
    resolve_preview_validated_assistant_text,
)

if TYPE_CHECKING:
    from core.agent.turn_state_writer import TurnStateWriter
    from core.types.json import JSONDict
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = (
    "TurnLoopToolSequenceState",
    "resolve_turn_loop_tool_calls",
)


@dataclass(slots=True)
class TurnLoopToolSequenceState:
    next_sequence_index: int
    content_index_offset: int = 0
    thinking_index_offset: int = 0

    @classmethod
    def from_turn_state_writer(
        cls,
        turn_state_writer: TurnStateWriter,
    ) -> TurnLoopToolSequenceState:
        return cls(
            next_sequence_index=resolve_next_tool_sequence_index(
                activities=turn_state_writer.latest_activities,
                tool_calls=turn_state_writer.latest_tool_calls,
            ),
            content_index_offset=_resolve_next_anchor(
                assistant_text=turn_state_writer.latest_assistant_text,
                activities=turn_state_writer.latest_activities,
                tool_calls=turn_state_writer.latest_tool_calls,
                field_name="content_index_before",
            ),
            thinking_index_offset=_resolve_next_anchor(
                assistant_text=None,
                activities=turn_state_writer.latest_activities,
                tool_calls=turn_state_writer.latest_tool_calls,
                field_name="thinking_index_before",
            ),
        )

    def allocate_next_sequence_index(self) -> int:
        sequence_index = self.next_sequence_index
        self.next_sequence_index = sequence_index + 1
        return sequence_index

    def reserve_detected_tool_calls(self, tool_calls: list[JSONDict]) -> None:
        self.next_sequence_index = max(
            self.next_sequence_index,
            resolve_next_tool_sequence_index(activities=[], tool_calls=tool_calls),
        )

    def apply_to_tool_calls(
        self,
        *,
        tool_calls: list[JSONDict],
        visible_text_chars: int,
        thinking_text_chars: int,
        pre_offset: bool,
    ) -> None:
        if not pre_offset:
            for tool_call in tool_calls:
                _offset_tool_call_anchor(
                    tool_call=tool_call,
                    field_name="content_index_before",
                    offset=self.content_index_offset,
                    upper_bound=self.content_index_offset + max(0, visible_text_chars),
                )
                _offset_tool_call_anchor(
                    tool_call=tool_call,
                    field_name="thinking_index_before",
                    offset=self.thinking_index_offset,
                    upper_bound=self.thinking_index_offset + max(0, thinking_text_chars),
                )
        if pre_offset:
            self.next_sequence_index = max(
                self.next_sequence_index,
                resolve_next_tool_sequence_index(activities=[], tool_calls=tool_calls),
            )
        else:
            self.next_sequence_index = apply_tool_sequence_offset(
                tool_calls=tool_calls,
                next_sequence_index=self.next_sequence_index,
            )
        self.content_index_offset += max(0, visible_text_chars)
        self.thinking_index_offset += max(0, thinking_text_chars)


def _offset_tool_call_anchor(
    *,
    tool_call: JSONDict,
    field_name: str,
    offset: int,
    upper_bound: int,
) -> None:
    if coerce_optional_non_negative_int_strict(tool_call.get(field_name)) is None:
        return
    tool_call[field_name] = offset_required_chronology_anchor(
        tool_call.get(field_name),
        field_name,
        offset=offset,
        upper_bound=upper_bound,
    )


def _resolve_next_anchor(
    *,
    assistant_text: str | None,
    activities: list[JSONDict],
    tool_calls: list[JSONDict],
    field_name: str,
) -> int:
    next_anchor = len(assistant_text) if assistant_text is not None else 0
    for entry in activities:
        next_anchor = max(next_anchor, _read_anchor(entry, field_name))
        if field_name == "content_index_before":
            next_anchor = max(next_anchor, _read_anchor(entry, "text_length_before"))
    for entry in tool_calls:
        next_anchor = max(next_anchor, _read_anchor(entry, field_name))
    return next_anchor


def _read_anchor(entry: JSONDict, field_name: str) -> int:
    value = coerce_optional_non_negative_int_strict(entry.get(field_name))
    return value if value is not None else 0


def _apply_text_tool_call_fallback(
    *,
    final_payload: JSONDict,
    offered_tool_names: frozenset[str],
) -> list[JSONDict]:
    if not offered_tool_names:
        return []
    choices = final_payload.get("choices")
    if not isinstance(choices, list):
        return []
    raw_tool_calls: list[JSONDict] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        extraction = extract_text_tool_calls(
            assistant_content=message.get("content"),
            offered_tool_names=offered_tool_names,
        )
        if not extraction.tool_calls:
            continue
        message["content"] = extraction.sanitized_text
        message["tool_calls"] = extraction.tool_calls
        raw_tool_calls.extend(extraction.tool_calls)
    if not raw_tool_calls:
        return []
    return extract_tool_calls_from_payload(final_payload)


def _extract_first_assistant_payload_text(final_payload: JSONDict) -> str | None:
    choices = final_payload.get("choices")
    if not isinstance(choices, list):
        return None
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        return render_openai_content_text(message.get("content"))
    return None


async def resolve_turn_loop_tool_calls(
    *,
    final_payload: JSONDict,
    assistant_text: str | None,
    assistant_output_published: bool,
    resolved_tool_calls: list[JSONDict],
    visible_text_chars: int,
    thinking_text_chars: int,
    tool_sequence_state: TurnLoopToolSequenceState,
    offered_tool_names: frozenset[str] = frozenset(),
    validate_visible_assistant_output: (
        Callable[
            [str],
            Awaitable[PreviewContractOutputValidationResult],
        ]
        | None
    ) = None,
) -> tuple[str | None, PreviewContractOutputValidationResult | None, list[JSONDict]]:
    if not assistant_output_published:
        resolved_assistant_text, preview_contract_validation = (
            await resolve_preview_validated_assistant_text(
                final_payload=final_payload,
                tool_calls=[],
                assistant_text=assistant_text,
                validate_visible_assistant_output=validate_visible_assistant_output,
            )
        )
        return resolved_assistant_text, preview_contract_validation, []
    pre_offset = bool(resolved_tool_calls)
    tool_calls = [dict(tool_call) for tool_call in resolved_tool_calls]
    resolved_visible_text_chars = max(0, visible_text_chars)
    resolved_thinking_text_chars = max(0, thinking_text_chars)
    if not pre_offset:
        tool_calls = extract_tool_calls_from_payload(final_payload)
        if not tool_calls:
            tool_calls = _apply_text_tool_call_fallback(
                final_payload=final_payload,
                offered_tool_names=offered_tool_names,
            )
            if tool_calls:
                assistant_text = _extract_first_assistant_payload_text(final_payload)
        resolved_visible_text_chars, resolved_thinking_text_chars = (
            extract_assistant_payload_text_lengths(final_payload)
        )
    resolved_assistant_text, preview_contract_validation = (
        await resolve_preview_validated_assistant_text(
            final_payload=final_payload,
            tool_calls=tool_calls,
            assistant_text=assistant_text,
            validate_visible_assistant_output=validate_visible_assistant_output,
        )
    )
    if not tool_calls:
        resolved_visible_text_chars, resolved_thinking_text_chars = (
            extract_assistant_payload_text_lengths(final_payload)
        )
    tool_sequence_state.apply_to_tool_calls(
        tool_calls=tool_calls,
        visible_text_chars=resolved_visible_text_chars,
        thinking_text_chars=resolved_thinking_text_chars,
        pre_offset=pre_offset,
    )
    return resolved_assistant_text, preview_contract_validation, tool_calls
