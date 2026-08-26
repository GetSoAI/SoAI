"""SoAI - Structured SSE block decoder for OpenAI-compatible streams [backend/core/openai/sse_block_decoder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.sse_frames import is_openai_sse_done_payload_text
from core.serialization.json_parsing import parse_json_value
from core.streaming.sse_frames import extract_sse_data_payload_text
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "DecodedSSEBlock",
    "DecodedSSEDataEvent",
    "decode_openai_sse_block",
    "is_valid_openai_decoded_block",
)


@dataclass(frozen=True, slots=True)
class DecodedSSEDataEvent:
    payload_text: str
    payload: JSONDict | None
    is_done: bool


@dataclass(frozen=True, slots=True)
class DecodedSSEBlock:
    normalized_text: str
    is_terminated: bool
    is_well_formed: bool
    data_events: tuple[DecodedSSEDataEvent, ...]

    @property
    def payloads(self) -> tuple[JSONDict, ...]:
        parsed_payloads: list[JSONDict] = []
        for event in self.data_events:
            if event.payload is not None:
                parsed_payloads.append(event.payload)
        return tuple(parsed_payloads)


def _split_sse_events(frame_text: str) -> tuple[tuple[str, ...], ...]:
    events: list[tuple[str, ...]] = []
    current_event_lines: list[str] = []
    for line in frame_text.split("\n"):
        if not line.strip():
            if current_event_lines:
                events.append(tuple(current_event_lines))
                current_event_lines.clear()
            continue
        current_event_lines.append(line)
    if current_event_lines:
        events.append(tuple(current_event_lines))
    return tuple(events)


def _split_sse_field(line: str) -> tuple[str, str]:
    separator_index = line.find(":")
    if separator_index < 0:
        return line, ""
    field_name = line[:separator_index]
    field_value = line[separator_index + 1 :]
    field_value = field_value.removeprefix(" ")
    return field_name, field_value


def decode_openai_sse_block(block: JSONValue) -> DecodedSSEBlock:
    if not isinstance(block, str):
        return DecodedSSEBlock(
            normalized_text="",
            is_terminated=False,
            is_well_formed=False,
            data_events=(),
        )
    normalized_text = block.replace("\r\n", "\n").replace("\r", "\n")
    is_terminated = normalized_text.endswith("\n\n")
    frame_text = normalized_text[:-2] if is_terminated else normalized_text
    if not frame_text.strip():
        return DecodedSSEBlock(
            normalized_text=normalized_text,
            is_terminated=is_terminated,
            is_well_formed=False,
            data_events=(),
        )
    events = _split_sse_events(frame_text)
    if not events:
        return DecodedSSEBlock(
            normalized_text=normalized_text,
            is_terminated=is_terminated,
            is_well_formed=False,
            data_events=(),
        )
    is_well_formed = True
    data_events: list[DecodedSSEDataEvent] = []
    for event_lines in events:
        data_lines: list[str] = []
        for line in event_lines:
            if line.startswith(":"):
                continue
            payload_text = extract_sse_data_payload_text(line)
            if payload_text is not None:
                data_lines.append(payload_text)
                continue
            field_name, _field_value = _split_sse_field(line)
            if field_name in {"event", "id", "retry"}:
                continue
        if not data_lines:
            continue
        payload_text = "\n".join(data_lines)
        if not payload_text.strip():
            is_well_formed = False
            continue
        if is_openai_sse_done_payload_text(payload_text):
            data_events.append(
                DecodedSSEDataEvent(payload_text=payload_text, payload=None, is_done=True),
            )
            continue
        parsed_payload: JSONDict | None = None
        try:
            loaded_payload = parse_json_value(payload_text)
            parsed_payload = coerce_json_dict(loaded_payload)
        except ValidationError:
            parsed_payload = None
        if parsed_payload is None:
            is_well_formed = False
        data_events.append(
            DecodedSSEDataEvent(payload_text=payload_text, payload=parsed_payload, is_done=False),
        )
    return DecodedSSEBlock(
        normalized_text=normalized_text,
        is_terminated=is_terminated,
        is_well_formed=is_well_formed,
        data_events=tuple(data_events),
    )


def is_valid_openai_decoded_block(
    decoded_block: DecodedSSEBlock,
    *,
    allow_responses_events: bool = False,
    allow_image_events: bool = False,
    allow_transcription_events: bool = False,
) -> bool:
    if not decoded_block.is_terminated:
        return False
    if not decoded_block.is_well_formed:
        return False
    for data_event in decoded_block.data_events:
        if data_event.is_done:
            continue
        payload = data_event.payload
        if payload is None:
            return False
        if allow_responses_events:
            if "type" in payload:
                event_type = payload.get("type")
                if not isinstance(event_type, str):
                    return False
                if not event_type.startswith("response."):
                    return False
                continue
            if "choices" in payload or "error" in payload:
                continue
            return False
        if allow_image_events:
            if "type" in payload:
                event_type = payload.get("type")
                if not isinstance(event_type, str):
                    return False
                if not (
                    event_type.startswith("image_generation.")
                    or event_type.startswith("image_edit.")
                    or event_type.startswith("image_variation.")
                ):
                    return False
                continue
            if "choices" in payload or "error" in payload:
                continue
            return False
        if allow_transcription_events:
            event_type = payload.get("type")
            if event_type in {
                "transcript.text.delta",
                "transcript.text.done",
            }:
                continue
            if "error" in payload:
                continue
            return False
        if "choices" in payload or "error" in payload:
            continue
        return False
    return True
