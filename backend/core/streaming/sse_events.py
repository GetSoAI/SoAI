"""SoAI - Generic Server-Sent Events decoding helpers [backend/core/streaming/sse_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass

__all__ = (
    "SSEEvent",
    "iter_sse_events",
)


@dataclass(frozen=True, slots=True)
class SSEEvent:
    event: str
    data: str
    event_id: str | None = None


async def iter_sse_events(lines: AsyncIterable[str]) -> AsyncIterator[SSEEvent]:
    event_name = "message"
    data_lines: list[str] = []
    event_id: str | None = None
    async for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if line == "":
            event = _build_event(event_name, data_lines, event_id)
            if event is not None:
                yield event
            event_name = "message"
            data_lines = []
            event_id = None
            continue
        if line.startswith(":"):
            continue
        field_name, separator, raw_value = line.partition(":")
        if not separator:
            value = ""
        elif raw_value.startswith(" "):
            value = raw_value[1:]
        else:
            value = raw_value
        if field_name == "event":
            event_name = value or "message"
            continue
        if field_name == "id":
            event_id = value or None
            continue
        if field_name == "data":
            data_lines.append(value)
    trailing_event = _build_event(event_name, data_lines, event_id)
    if trailing_event is not None:
        yield trailing_event


def _build_event(event_name: str, data_lines: list[str], event_id: str | None) -> SSEEvent | None:
    if not data_lines:
        return None
    return SSEEvent(event=event_name or "message", data="\n".join(data_lines), event_id=event_id)
