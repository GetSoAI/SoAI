"""SoAI - Agent streamed tool detection publication [backend/features/agent/runtime/streaming_tool_detection_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from core.types.json import JSONDict
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

__all__ = ("StreamingToolDetectionPublication",)


@dataclass(slots=True)
class StreamingToolDetectionPublication:
    callback: Callable[[tuple[JSONDict, ...]], Awaitable[None] | None] | None
    content_index_base: int
    detected_calls: list[JSONDict] = field(default_factory=list[JSONDict])
    pending_calls: list[JSONDict] = field(default_factory=list[JSONDict])

    async def record(
        self,
        calls: tuple[JSONDict, ...],
        *,
        hold: bool,
        removed_chars: int,
    ) -> None:
        if hold:
            self.pending_calls.extend(dict(call) for call in calls)
            return
        await self._publish(calls, removed_chars=removed_chars)

    async def flush(self, *, removed_chars: int) -> None:
        if not self.pending_calls:
            return
        calls = tuple(self.pending_calls)
        self.pending_calls.clear()
        await self._publish(calls, removed_chars=removed_chars)

    async def _publish(self, calls: tuple[JSONDict, ...], *, removed_chars: int) -> None:
        adjusted = self.adjust_calls(list(calls), removed_chars=removed_chars)
        self.detected_calls.extend(adjusted)
        if self.callback is not None:
            result = self.callback(tuple(adjusted))
            if result is not None:
                await result

    def adjust_calls(self, calls: list[JSONDict], *, removed_chars: int) -> list[JSONDict]:
        adjusted: list[JSONDict] = []
        for call in calls:
            published = dict(call)
            anchor = coerce_optional_non_negative_int_strict(published.get("content_index_before"))
            if anchor is not None and removed_chars:
                published["content_index_before"] = max(
                    self.content_index_base,
                    anchor - removed_chars,
                )
            adjusted.append(published)
        return adjusted
