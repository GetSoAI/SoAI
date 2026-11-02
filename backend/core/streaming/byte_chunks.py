"""SoAI - Bounded byte batching with receive progress [backend/core/streaming/byte_chunks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

from core.validation.strict_numbers import require_positive_int_strict

__all__ = ("iter_batched_byte_chunks",)


def iter_batched_byte_chunks(
    chunks: Iterable[bytes],
    *,
    chunk_size: int,
    on_progress: Callable[[int], None] | None = None,
) -> Iterator[bytes]:
    require_positive_int_strict(chunk_size, error_message="Chunk size must be positive.")
    pending = bytearray()
    received_bytes = 0
    for chunk in chunks:
        if not chunk:
            continue
        received_bytes += len(chunk)
        if on_progress is not None:
            on_progress(received_bytes)
        offset = 0
        while offset < len(chunk):
            consumed = min(chunk_size - len(pending), len(chunk) - offset)
            pending.extend(chunk[offset : offset + consumed])
            offset += consumed
            if len(pending) == chunk_size:
                yield bytes(pending)
                pending.clear()
    if pending:
        yield bytes(pending)
