"""SoAI - OpenAI stream text classification [backend/core/openai/stream_transcript/text_classifier.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.openai.stream_transcript.payload_segments import (
    extract_reasoning_text_from_source,
    iter_text_segments_from_payload,
)
from core.openai.tool_call_stream_matching import (
    THINKING_CLOSE_TAG_REGEX,
    THINKING_OPEN_TAG_REGEX,
)
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("OpenAIStreamTextClassifier",)


def _shared_prefix_length(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


class OpenAIStreamTextClassifier:
    def __init__(
        self,
        *,
        clock_ms: Callable[[], int] = monotonic_ms,
    ) -> None:
        self._clock_ms = clock_ms
        self._visible_text_parts: list[str] = []
        self._visible_text_deltas: list[str] = []
        self._completion_token_fragments: list[str] = []
        self._visible_content_chars = 0
        self._thinking_text_parts: list[str] = []
        self._thinking_text_deltas: list[str] = []
        self._thinking_chars = 0
        self._has_thinking_content = False
        self._last_thinking_close_visible_chars: int | None = None
        self._thinking_buffer = ""
        self._thinking_depth = 0
        self._last_thinking_boundary_ms: int | None = None
        self._thinking_tail_duration_ms: int | None = None
        self._thinking_close_events = 0
        self._reasoning_mirror = ""
        self._reasoning_mirror_cursor = 0
        self._pending_visible_candidates: deque[str] = deque()

    def _get_visible_content_with_pending_char_count(self) -> int:
        pending_chars = sum(len(text) for text in self._pending_visible_candidates)
        return self._visible_content_chars + pending_chars

    def _note_thinking_boundary_started_if_missing(self) -> None:
        if self._last_thinking_boundary_ms is not None:
            return
        self._thinking_tail_duration_ms = None
        self._last_thinking_boundary_ms = int(self._clock_ms())

    def _note_thinking_boundary_closed(self) -> None:
        boundary_ms = self._last_thinking_boundary_ms
        if boundary_ms is not None:
            now_ms = int(self._clock_ms())
            self._thinking_tail_duration_ms = max(0, now_ms - boundary_ms)
        self._last_thinking_boundary_ms = None
        self._thinking_close_events += 1

    def _resolve_elapsed_since_last_thinking_boundary_ms(self) -> int:
        boundary_ms = self._last_thinking_boundary_ms
        if boundary_ms is None:
            return 0
        now_ms = int(self._clock_ms())
        return max(0, now_ms - boundary_ms)

    def _append_visible_text(self, text: str) -> None:
        if not text:
            return
        should_close_thinking_boundary = (
            self._has_thinking_content
            and self._last_thinking_close_visible_chars is None
            and self._thinking_depth == 0
        )
        if should_close_thinking_boundary:
            self._last_thinking_close_visible_chars = self._visible_content_chars
        self._visible_text_parts.append(text)
        self._visible_text_deltas.append(text)
        self._completion_token_fragments.append(text)
        self._visible_content_chars += len(text)
        if should_close_thinking_boundary:
            self._note_thinking_boundary_closed()

    def _append_thinking_text(self, text: str) -> None:
        if not text:
            return
        self._note_thinking_boundary_started_if_missing()
        self._has_thinking_content = True
        self._thinking_text_parts.append(text)
        self._thinking_text_deltas.append(text)
        self._completion_token_fragments.append(text)
        self._thinking_chars += len(text)

    def _append_reasoning_mirror(self, text: str) -> None:
        if not text:
            return
        self._reasoning_mirror += text
        self._trim_reasoning_mirror_if_needed()

    def _trim_reasoning_mirror_if_needed(self) -> None:
        if self._reasoning_mirror_cursor <= 0:
            return
        remaining = len(self._reasoning_mirror) - self._reasoning_mirror_cursor
        if self._reasoning_mirror_cursor < 4096 and self._reasoning_mirror_cursor < remaining:
            return
        self._reasoning_mirror = self._reasoning_mirror[self._reasoning_mirror_cursor :]
        self._reasoning_mirror_cursor = 0

    def _resolve_pending_visible_candidates(self, *, force_visible: bool) -> None:
        while self._pending_visible_candidates:
            unread_reasoning = self._reasoning_mirror[self._reasoning_mirror_cursor :]
            if not unread_reasoning:
                self._flush_pending_candidates_as_visible()
                return
            pending_text = "".join(self._pending_visible_candidates)
            shared = _shared_prefix_length(pending_text, unread_reasoning)
            if shared >= len(unread_reasoning):
                self._discard_reasoning_echo_prefix(len(unread_reasoning))
                continue
            if shared == len(pending_text):
                if force_visible:
                    self._flush_pending_candidates_as_visible()
                return
            self._flush_pending_candidates_as_visible()
            return

    def _discard_reasoning_echo_prefix(self, echo_length: int) -> None:
        remaining = echo_length
        while remaining > 0 and self._pending_visible_candidates:
            head = self._pending_visible_candidates[0]
            if len(head) <= remaining:
                self._pending_visible_candidates.popleft()
                remaining -= len(head)
                continue
            self._pending_visible_candidates[0] = head[remaining:]
            remaining = 0
        self._reasoning_mirror_cursor += echo_length
        self._trim_reasoning_mirror_if_needed()

    def _flush_pending_candidates_as_visible(self) -> None:
        while self._pending_visible_candidates:
            self._append_visible_text(self._pending_visible_candidates.popleft())

    def _stage_visible_candidate(self, text: str) -> None:
        if not text:
            return
        self._pending_visible_candidates.append(text)
        self._resolve_pending_visible_candidates(force_visible=False)

    def consume_reasoning_text(self, text: str) -> None:
        if not text:
            return
        self._append_thinking_text(text)
        self._append_reasoning_mirror(text)
        self._resolve_pending_visible_candidates(force_visible=False)

    def consume_content_text(self, text: str) -> None:
        if not text:
            return
        source = f"{self._thinking_buffer}{text}"
        self._thinking_buffer = ""
        cursor = 0
        while cursor < len(source):
            tag_index = source.find("<", cursor)
            if tag_index == -1:
                chunk = source[cursor:]
                if self._thinking_depth > 0:
                    self._append_thinking_text(chunk)
                else:
                    self._stage_visible_candidate(chunk)
                break
            if tag_index > cursor:
                chunk = source[cursor:tag_index]
                if self._thinking_depth > 0:
                    self._append_thinking_text(chunk)
                else:
                    self._stage_visible_candidate(chunk)
            close_index = source.find(">", tag_index + 1)
            if close_index == -1:
                self._thinking_buffer = source[tag_index:]
                break
            tag_text = source[tag_index : close_index + 1]
            normalized_tag_text = tag_text.lower()
            if re.match(THINKING_OPEN_TAG_REGEX, normalized_tag_text):
                self._has_thinking_content = True
                self._thinking_depth += 1
            elif re.match(THINKING_CLOSE_TAG_REGEX, normalized_tag_text):
                if self._thinking_depth > 0:
                    self._thinking_depth -= 1
                    if self._thinking_depth == 0:
                        self._last_thinking_close_visible_chars = (
                            self._get_visible_content_with_pending_char_count()
                        )
                        self._note_thinking_boundary_closed()
                else:
                    self._stage_visible_candidate(tag_text)
            elif self._thinking_depth > 0:
                self._append_thinking_text(tag_text)
            else:
                self._stage_visible_candidate(tag_text)
            cursor = close_index + 1

    def consume_text_source(self, source: JSONDict) -> None:
        reasoning_text = extract_reasoning_text_from_source(source)
        if reasoning_text:
            self.consume_reasoning_text(reasoning_text)
        if "content" not in source:
            return
        for segment in iter_text_segments_from_payload(source.get("content")):
            if segment.channel == "thinking":
                self.consume_reasoning_text(segment.text)
                continue
            self.consume_content_text(segment.text)

    def flush_for_tool_call_boundary(self) -> None:
        self._resolve_pending_visible_candidates(force_visible=True)

    def _flush_unclosed_tag_buffer(self) -> None:
        if not self._thinking_buffer:
            return
        buffered = self._thinking_buffer
        self._thinking_buffer = ""
        if self._thinking_depth > 0:
            self._append_thinking_text(buffered)
            return
        self._stage_visible_candidate(buffered)

    def finalize(self) -> None:
        self._flush_unclosed_tag_buffer()
        self._resolve_pending_visible_candidates(force_visible=True)
        if self._thinking_tail_duration_ms is None:
            self._thinking_tail_duration_ms = (
                self._resolve_elapsed_since_last_thinking_boundary_ms()
            )

    def drain_visible_text_deltas(self) -> tuple[str, ...]:
        self._resolve_pending_visible_candidates(force_visible=False)
        drained = tuple(self._visible_text_deltas)
        self._visible_text_deltas.clear()
        return drained

    def drain_thinking_text_deltas(self) -> tuple[str, ...]:
        drained = tuple(self._thinking_text_deltas)
        self._thinking_text_deltas.clear()
        return drained

    def drain_completion_token_fragments(self) -> tuple[str, ...]:
        drained = tuple(self._completion_token_fragments)
        self._completion_token_fragments.clear()
        return drained

    def get_visible_text(self) -> str:
        return "".join(self._visible_text_parts)

    def get_thinking_text(self) -> str:
        return "".join(self._thinking_text_parts)

    def get_thinking_tail_duration_ms(self) -> int:
        if self._thinking_tail_duration_ms is None:
            return self._resolve_elapsed_since_last_thinking_boundary_ms()
        return int(self._thinking_tail_duration_ms)

    def get_thinking_tail_content_index_before(self) -> int:
        if self._visible_content_chars <= 0:
            return 0
        marker = self._last_thinking_close_visible_chars
        if marker is None:
            return max(0, self._visible_content_chars)
        return max(0, min(self._visible_content_chars, marker))

    def get_visible_content_char_count(self) -> int:
        return int(self._visible_content_chars)

    def get_thinking_char_count(self) -> int:
        return int(self._thinking_chars)

    def drain_thinking_close_events(self) -> int:
        drained = int(self._thinking_close_events)
        self._thinking_close_events = 0
        return drained
