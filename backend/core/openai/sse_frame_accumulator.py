"""SoAI - Strict OpenAI SSE frame accumulation [backend/core/openai/sse_frame_accumulator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ModelOutputContractError, StateError, ValidationError
from core.openai.stream_chunk_bytes import coerce_stream_chunk_to_bytes

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk

__all__ = ("OpenAISSEFrameAccumulator",)


class OpenAISSEFrameAccumulator:
    __slots__ = (
        "_buffer_limit_bytes",
        "_finalized",
        "_pending_bytes",
        "_pending_carriage_return",
    )

    def __init__(self, *, buffer_limit_bytes: int = MIB_BYTES) -> None:
        if (
            isinstance(buffer_limit_bytes, bool)
            or not isinstance(buffer_limit_bytes, int)
            or buffer_limit_bytes <= 0
        ):
            raise ValidationError("OpenAI SSE buffer limit must be a positive integer.")
        self._buffer_limit_bytes = buffer_limit_bytes
        self._finalized = False
        self._pending_bytes = bytearray()
        self._pending_carriage_return = False

    def feed(self, chunk: StreamChunk) -> tuple[str, ...]:
        if self._finalized:
            raise StateError("OpenAI SSE frame accumulator is already finalized.")
        chunk_bytes = coerce_stream_chunk_to_bytes(chunk)
        normalized_bytes, pending_carriage_return = _normalize_line_endings(
            chunk_bytes,
            pending_carriage_return=self._pending_carriage_return,
        )
        candidate = bytearray(self._pending_bytes)
        candidate.extend(normalized_bytes)
        frames: list[str] = []
        consumed_offset = 0
        while True:
            delimiter_index = candidate.find(b"\n\n", consumed_offset)
            if delimiter_index < 0:
                break
            frame_size = delimiter_index - consumed_offset
            if frame_size > self._buffer_limit_bytes:
                raise ModelOutputContractError(
                    "OpenAI SSE frame exceeded the pending buffer limit.",
                    details={
                        "buffer_limit_bytes": self._buffer_limit_bytes,
                        "failure_type": "frame_too_large",
                    },
                )
            frame_bytes = bytes(candidate[consumed_offset:delimiter_index]) + b"\n\n"
            try:
                frames.append(frame_bytes.decode("utf-8"))
            except UnicodeDecodeError as exception:
                raise ModelOutputContractError(
                    "OpenAI SSE frame contains invalid UTF-8.",
                    details={"failure_type": "invalid_utf8"},
                    cause=exception,
                ) from exception
            consumed_offset = delimiter_index + 2
        remainder = candidate[consumed_offset:]
        pending_size = len(remainder)
        if pending_size > self._buffer_limit_bytes:
            raise ModelOutputContractError(
                "OpenAI SSE frame exceeded the pending buffer limit.",
                details={
                    "buffer_limit_bytes": self._buffer_limit_bytes,
                    "failure_type": "frame_too_large",
                },
            )
        self._pending_bytes = remainder
        self._pending_carriage_return = pending_carriage_return
        return tuple(frames)

    def finalize(self) -> None:
        if self._finalized:
            return
        candidate = bytearray(self._pending_bytes)
        if candidate:
            try:
                candidate.decode("utf-8")
            except UnicodeDecodeError as exception:
                raise ModelOutputContractError(
                    "OpenAI SSE stream ended with invalid UTF-8.",
                    details={"failure_type": "invalid_utf8"},
                    cause=exception,
                ) from exception
            raise ModelOutputContractError(
                "OpenAI SSE stream ended with an unterminated frame.",
                details={"failure_type": "unterminated_frame"},
            )
        self._pending_bytes.clear()
        self._pending_carriage_return = False
        self._finalized = True

    def pending_byte_count(self) -> int:
        return len(self._pending_bytes)


def _normalize_line_endings(
    chunk_bytes: bytes,
    *,
    pending_carriage_return: bool,
) -> tuple[bytes, bool]:
    normalized = bytearray()
    offset = 0
    if pending_carriage_return:
        if not chunk_bytes:
            return (b"", True)
        if chunk_bytes.startswith(b"\n"):
            offset = 1
    pending_carriage_return = False
    while offset < len(chunk_bytes):
        byte_value = chunk_bytes[offset]
        if byte_value != 13:
            normalized.append(byte_value)
            offset += 1
            continue
        normalized.append(10)
        if offset + 1 >= len(chunk_bytes):
            pending_carriage_return = True
            offset += 1
            continue
        offset += 2 if chunk_bytes[offset + 1] == 10 else 1
    return (bytes(normalized), pending_carriage_return)
