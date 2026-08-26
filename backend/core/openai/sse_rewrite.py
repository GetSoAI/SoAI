"""SoAI - OpenAI SSE frame payload rewriting [backend/core/openai/sse_rewrite.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ModelOutputContractError
from core.openai.sse_block_decoder import decode_openai_sse_block
from core.serialization.json import serialize_json_compact_stable_strict
from core.streaming.sse_frames import SSE_DATA_PREFIX, extract_sse_data_payload_text

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("rewrite_openai_sse_json_payload_frame",)


def rewrite_openai_sse_json_payload_frame(
    frame: bytes,
    *,
    rewrite_payload: Callable[[JSONDict], bool],
) -> bytes:
    try:
        decoded = frame.decode("utf-8")
    except UnicodeDecodeError as exception:
        raise ModelOutputContractError(
            "OpenAI SSE frame contains invalid UTF-8.",
            details={"failure_type": "invalid_utf8"},
            cause=exception,
        ) from exception

    decoded_frame = decode_openai_sse_block(decoded)
    if not decoded_frame.is_terminated or not decoded_frame.is_well_formed:
        raise ModelOutputContractError(
            "Provider returned a malformed OpenAI SSE frame.",
            details={"failure_type": "malformed_frame"},
        )
    data_events = decoded_frame.data_events
    if not data_events or all(event.is_done for event in data_events):
        return frame
    if len(data_events) != 1:
        raise ModelOutputContractError(
            "OpenAI SSE frame contains multiple data events.",
            details={"failure_type": "multiple_data_events"},
        )
    data_event = data_events[0]
    payload = data_event.payload
    if payload is None or isinstance(payload.get("error"), dict):
        return frame
    if not rewrite_payload(payload):
        return frame

    frame_lines = decoded_frame.normalized_text[:-2].split("\n")
    data_line_indexes = [
        index
        for index, line in enumerate(frame_lines)
        if extract_sse_data_payload_text(line) is not None
    ]
    if not data_line_indexes:
        raise ModelOutputContractError(
            "OpenAI SSE frame contains no data field.",
            details={"failure_type": "missing_data_field"},
        )
    first_data_line_index = data_line_indexes[0]
    rewritten_lines = [
        line
        for index, line in enumerate(frame_lines)
        if index == first_data_line_index or index not in data_line_indexes
    ]
    rewritten_lines[first_data_line_index] = (
        f"{SSE_DATA_PREFIX}{serialize_json_compact_stable_strict(payload)}"
    )
    rewritten_frame = "\n".join(rewritten_lines)
    return f"{rewritten_frame}\n\n".encode("utf-8")
