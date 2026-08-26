"""SoAI - Generic Server-Sent Events frame helpers [backend/core/streaming/sse_frames.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "extract_sse_data_payload_text",
    "format_sse_data_frame",
    "format_sse_heartbeat_frame",
    "format_sse_named_data_frame",
)

SSE_DATA_FIELD_PREFIX: str = "data:"
SSE_DATA_PREFIX: str = "data: "
SSE_EVENT_TERMINATOR: str = "\n\n"


def extract_sse_data_payload_text(line: str) -> str | None:
    line_text = line.rstrip("\r\n")
    if not line_text.startswith(SSE_DATA_FIELD_PREFIX):
        return None
    payload_text = line_text[len(SSE_DATA_FIELD_PREFIX) :]
    if payload_text.startswith(" "):
        return payload_text[1:]
    return payload_text


def format_sse_data_frame(serialized_payload: str) -> str:
    return f"{SSE_DATA_PREFIX}{serialized_payload}{SSE_EVENT_TERMINATOR}"


def format_sse_named_data_frame(
    *,
    serialized_payload: str,
    event_name: str,
    event_id: str | None = None,
) -> str:
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_name}")
    lines.append(f"{SSE_DATA_PREFIX}{serialized_payload}")
    return "\n".join(lines) + SSE_EVENT_TERMINATOR


def format_sse_heartbeat_frame(label: str = "heartbeat") -> str:
    return f": {label}{SSE_EVENT_TERMINATOR}"
