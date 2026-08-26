"""SoAI - OpenAI SSE event formatting helpers [backend/core/openai/sse_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from core.openai.openai_error_objects import build_openai_error_payload
from core.openai.sse_frames import is_openai_sse_done_payload_text
from core.serialization.json import serialize_json_compact_stable_strict
from core.streaming.sse_frames import (
    extract_sse_data_payload_text,
    format_sse_data_frame,
)
from core.types.json import JSONValue

__all__ = (
    "chunk_contains_done_marker",
    "format_openai_sse_bytes",
    "format_openai_sse_data",
    "format_openai_storage_error_chunk",
    "format_openai_stream_error_chunk",
    "strip_done_marker_lines",
)


def format_openai_sse_data(payload: JSONValue) -> str:
    return format_sse_data_frame(serialize_json_compact_stable_strict(payload))


def format_openai_sse_bytes(payload: JSONValue) -> bytes:
    return format_openai_sse_data(payload).encode("utf-8")


def format_openai_storage_error_chunk(message: str) -> bytes:
    payload = build_openai_error_payload(
        message=message,
        error_type="server_error",
        param=None,
        code="storage_failed",
    )
    return format_openai_sse_data(payload).encode("utf-8")


def chunk_contains_done_marker(chunk_text: str) -> bool:
    for line in chunk_text.splitlines():
        payload_text = extract_sse_data_payload_text(line)
        if payload_text is not None and is_openai_sse_done_payload_text(payload_text):
            return True
    return False


def strip_done_marker_lines(chunk_text: str) -> str:
    lines = chunk_text.splitlines(keepends=True)
    filtered_lines: list[str] = []
    skip_blank = False
    for line in lines:
        payload_text = extract_sse_data_payload_text(line)
        if payload_text is not None and is_openai_sse_done_payload_text(payload_text):
            skip_blank = True
            continue
        if skip_blank:
            if not line.strip():
                skip_blank = False
                continue
            skip_blank = False
        filtered_lines.append(line)
    return "".join(filtered_lines)


def format_openai_stream_error_chunk(
    format_error_chunk: Callable[[str, str, str], str | bytes] | None,
    message: str,
    error_type: str,
    trace_id: str,
) -> bytes:
    if format_error_chunk is None:
        payload = build_openai_error_payload(
            message=message,
            error_type=error_type,
            param=None,
            code=None,
        )
        return format_openai_sse_data(payload).encode("utf-8")
    rendered = format_error_chunk(message, error_type, trace_id)
    if isinstance(rendered, bytes):
        return rendered
    return rendered.encode("utf-8")
