"""SoAI - Streamed injected prompt echo removal [backend/features/agent/runtime/injected_prompt_echo_stream_rewrite.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Iterator

from core.errors.exceptions import ModelOutputContractError
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads
from core.openai.sse_rewrite import rewrite_openai_sse_json_payload_frame
from core.openai.stream_transcript.payload_segments import (
    iter_text_segment_locations_from_payload,
)
from core.openai.stream_transcript.types import StreamTextSegmentLocation
from core.openai.tool_call_stream_matching import (
    THINKING_CLOSE_TAG_REGEX,
    THINKING_OPEN_TAG_REGEX,
)
from core.types.json import JSONDict
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.agent.runtime.injected_prompt_echo_stripping import (
    strip_echoed_injected_prompt_blocks,
)

__all__ = ("InjectedPromptEchoStreamRewriter",)


def _iter_visible_content_locations(
    source: JSONDict,
    field_name: str,
) -> Iterator[StreamTextSegmentLocation]:
    for location in iter_text_segment_locations_from_payload(
        source.get(field_name),
        container=source,
        key=field_name,
    ):
        if location.segment.channel == "visible":
            yield location


def _iter_incremental_content_locations(payload: JSONDict) -> Iterator[StreamTextSegmentLocation]:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        if "content" in payload:
            yield from _iter_visible_content_locations(payload, "content")
        return
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        has_delta_content = isinstance(delta, dict) and "content" in delta
        if isinstance(delta, dict):
            for field_name in ("content", "text"):
                if field_name in delta:
                    yield from _iter_visible_content_locations(delta, field_name)
        if not has_delta_content and "text" in choice:
            yield from _iter_visible_content_locations(choice, "text")


def _iter_message_content_groups(
    payload: JSONDict,
) -> Iterator[tuple[StreamTextSegmentLocation, ...]]:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if isinstance(message, dict) and "content" in message:
            yield tuple(_iter_visible_content_locations(message, "content"))


def _replace_content_locations(
    locations: tuple[StreamTextSegmentLocation, ...],
    replacements: Iterator[str],
) -> bool:
    changed = False
    for location in locations:
        rewritten = next(replacements)
        if rewritten == location.segment.text:
            continue
        container = location.container
        key = location.key
        if isinstance(container, dict) and isinstance(key, str):
            container[key] = rewritten
        elif isinstance(container, list) and isinstance(key, int):
            container[key] = rewritten
        else:
            raise ModelOutputContractError("Stream content location is invalid.")
        changed = True
    return changed


class InjectedPromptEchoStreamRewriter:
    def __init__(self, *, removed_visible_text: str, content_index_base: int) -> None:
        self._removed_visible_text = removed_visible_text
        self._removed_chars = len(removed_visible_text)
        self._content_index_base = content_index_base
        self._accumulator = OpenAISSEFrameAccumulator()

    def rewrite_buffered_chunks(self, chunks: tuple[bytes, ...]) -> tuple[bytes, ...]:
        frame_content_values: list[list[str]] = []
        snapshot_prefix_found = False
        for chunk in chunks:
            content_values: list[str] = []
            for payload in parse_openai_sse_frame_payloads(chunk):
                content_values.extend(
                    location.segment.text
                    for location in _iter_incremental_content_locations(payload)
                )
                for locations in _iter_message_content_groups(payload):
                    _rewritten, matched = self._remove_visible_prefix_from_fields(
                        [location.segment.text for location in locations],
                        allow_missing=True,
                    )
                    snapshot_prefix_found = snapshot_prefix_found or matched
            frame_content_values.append(content_values)

        flat_content_values = [
            value for frame_values in frame_content_values for value in frame_values
        ]
        rewritten_content_values, incremental_prefix_found = (
            self._remove_visible_prefix_from_fields(
                flat_content_values,
                allow_missing=snapshot_prefix_found,
                allow_partial=snapshot_prefix_found,
            )
        )
        if not incremental_prefix_found and not snapshot_prefix_found:
            raise ModelOutputContractError(
                "Injected prompt echo could not be mapped to streamed content.",
                details={"failure_type": "unmapped_echo_prefix"},
            )
        rewritten_chunks: list[bytes] = []
        value_offset = 0
        for chunk, frame_values in zip(chunks, frame_content_values, strict=True):
            next_value_offset = value_offset + len(frame_values)
            frame_replacements = iter(rewritten_content_values[value_offset:next_value_offset])
            rewritten_chunks.append(
                self._rewrite_buffered_chunk(chunk, frame_replacements),
            )
            value_offset = next_value_offset
        return tuple(rewritten_chunks)

    def _rewrite_buffered_chunk(
        self,
        chunk: bytes,
        content_replacements: Iterator[str],
    ) -> bytes:
        return rewrite_openai_sse_json_payload_frame(
            chunk,
            rewrite_payload=lambda payload: self._rewrite_payload(
                payload,
                content_replacements=content_replacements,
            ),
        )

    def feed(self, chunk: bytes) -> tuple[bytes, ...]:
        return tuple(
            rewrite_openai_sse_json_payload_frame(
                frame.encode("utf-8"),
                rewrite_payload=self._rewrite_payload,
            )
            for frame in self._accumulator.feed(chunk)
        )

    def finalize(self) -> None:
        self._accumulator.finalize()

    def _rewrite_payload(
        self,
        payload: JSONDict,
        *,
        content_replacements: Iterator[str] | None = None,
    ) -> bool:
        changed = False
        if content_replacements is not None:
            changed = _replace_content_locations(
                tuple(_iter_incremental_content_locations(payload)),
                content_replacements,
            )
        choices = payload.get("choices")
        if not isinstance(choices, list):
            return changed
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if isinstance(delta, dict):
                changed = self._rewrite_tool_anchors(delta) or changed
            message = choice.get("message")
            if isinstance(message, dict):
                changed = self._rewrite_snapshot_content(message) or changed
                changed = self._rewrite_tool_anchors(message) or changed
        return changed

    def _rewrite_snapshot_content(self, message: JSONDict) -> bool:
        locations = tuple(_iter_visible_content_locations(message, "content"))
        rewritten, _matched = self._remove_visible_prefix_from_fields(
            [location.segment.text for location in locations],
            allow_missing=True,
        )
        changed = _replace_content_locations(locations, iter(rewritten))
        content_value = message.get("content")
        if isinstance(content_value, str):
            stripping = strip_echoed_injected_prompt_blocks(content_value)
            if stripping.stripped:
                message["content"] = stripping.sanitized_text
                changed = True
        return changed

    def _remove_visible_prefix_from_fields(
        self,
        content_values: list[str],
        *,
        allow_missing: bool = False,
        allow_partial: bool = False,
    ) -> tuple[tuple[str, ...], bool]:
        combined_content = "".join(content_values)
        visible_offsets: list[int] = []
        thinking_depth = 0
        cursor = 0
        while cursor < len(combined_content):
            if combined_content[cursor] == "<":
                close_index = combined_content.find(">", cursor + 1)
                if close_index >= 0:
                    tag = combined_content[cursor : close_index + 1]
                    if re.match(THINKING_OPEN_TAG_REGEX, tag, re.IGNORECASE):
                        thinking_depth += 1
                        cursor = close_index + 1
                        continue
                    if re.match(THINKING_CLOSE_TAG_REGEX, tag, re.IGNORECASE):
                        thinking_depth = max(0, thinking_depth - 1)
                        cursor = close_index + 1
                        continue
            if thinking_depth == 0:
                visible_offsets.append(cursor)
            cursor += 1

        visible_content = "".join(combined_content[index] for index in visible_offsets)
        visible_start = visible_content.find(self._removed_visible_text)
        if visible_start < 0:
            if allow_missing and (not allow_partial or not visible_content):
                return tuple(content_values), False
            if (
                not allow_partial
                or not visible_content
                or not self._removed_visible_text.startswith(visible_content)
            ):
                raise ModelOutputContractError(
                    "Injected prompt echo could not be mapped to streamed content.",
                    details={"failure_type": "unmapped_echo_prefix"},
                )
            selected_offsets = visible_offsets
        else:
            if visible_content.find(self._removed_visible_text, visible_start + 1) >= 0:
                raise ModelOutputContractError(
                    "Injected prompt echo maps to multiple streamed content positions.",
                    details={"failure_type": "ambiguous_echo_prefix"},
                )
            selected_offsets = visible_offsets[visible_start : visible_start + self._removed_chars]
        retained_chars = [True] * len(combined_content)
        for content_index in selected_offsets:
            retained_chars[content_index] = False

        rewritten_values: list[str] = []
        content_offset = 0
        for value in content_values:
            next_offset = content_offset + len(value)
            rewritten_values.append(
                "".join(
                    char
                    for index, char in enumerate(value, start=content_offset)
                    if retained_chars[index]
                ),
            )
            content_offset = next_offset
        return tuple(rewritten_values), True

    def _rewrite_tool_anchors(self, source: JSONDict) -> bool:
        calls = source.get("tool_calls")
        if not isinstance(calls, list) or self._removed_chars == 0:
            return False
        changed = False
        for call in calls:
            if not isinstance(call, dict):
                continue
            anchor = coerce_optional_non_negative_int_strict(call.get("content_index_before"))
            if anchor is None:
                continue
            call["content_index_before"] = max(
                self._content_index_base,
                anchor - self._removed_chars,
            )
            changed = True
        return changed
