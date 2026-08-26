"""SoAI - Stream chunk batching for coalesced delivery [backend/features/api/streaming/chunk_batcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time

from core.events.types_models_streaming import StreamChunkEvent

__all__ = ("StreamChunkBatcher",)

STREAM_CHUNK_BATCH_MAX_BYTES: int = 32768
STREAM_CHUNK_BATCH_MAX_DELAY_SEC: float = 0.02
STREAM_CHUNK_BATCH_MAX_ITEMS: int = 50


class StreamChunkBatcher:
    __slots__ = ("_chunks", "_first_chunk_time", "_total_bytes")

    def __init__(self) -> None:
        self._chunks: list[bytes] = []
        self._total_bytes: int = 0
        self._first_chunk_time: float | None = None

    def add(self, chunk: bytes) -> None:
        if not self._chunks:
            self._first_chunk_time = time.monotonic()
        self._chunks.append(chunk)
        self._total_bytes += len(chunk)

    def should_flush(self) -> bool:
        if not self._chunks:
            return False
        if self._total_bytes >= STREAM_CHUNK_BATCH_MAX_BYTES:
            return True
        if len(self._chunks) >= STREAM_CHUNK_BATCH_MAX_ITEMS:
            return True
        if self._first_chunk_time is not None:
            elapsed = time.monotonic() - self._first_chunk_time
            if elapsed >= STREAM_CHUNK_BATCH_MAX_DELAY_SEC:
                return True
        return False

    def flush(self) -> StreamChunkEvent | None:
        if not self._chunks:
            return None
        coalesced_data = b"".join(self._chunks)
        coalesced_event = StreamChunkEvent(chunk=coalesced_data)
        self._chunks = []
        self._total_bytes = 0
        self._first_chunk_time = None
        return coalesced_event

    def pending_count(self) -> int:
        return len(self._chunks)

    def has_pending(self) -> bool:
        return bool(self._chunks)
