"""SoAI - Bounded CSV preview collector for WebSocket exports [backend/features/api/routes/system/events/snapshots/csv_export_preview.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import codecs
from collections.abc import AsyncIterator

from core.errors.exceptions import ValidationError

__all__ = ("collect_csv_preview_text",)


async def collect_csv_preview_text(
    csv_bytes: AsyncIterator[bytes],
    *,
    max_bytes: int,
) -> tuple[str, bool]:
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValidationError("CSV preview max_bytes must be a positive integer")

    output = bytearray()
    async for chunk in csv_bytes:
        if not isinstance(chunk, bytes | bytearray):
            raise ValidationError("CSV stream yielded invalid chunk type")
        remaining = max_bytes - len(output)
        if remaining <= 0:
            return _decode_preview_bytes(bytes(output), truncated=True), True
        if len(chunk) <= remaining:
            output.extend(chunk)
            continue
        output.extend(chunk[:remaining])
        return _decode_preview_bytes(bytes(output), truncated=True), True

    return _decode_preview_bytes(bytes(output), truncated=False), False


def _decode_preview_bytes(raw: bytes, *, truncated: bool) -> str:
    try:
        decoder_factory = codecs.getincrementaldecoder("utf-8")
        decoder = decoder_factory()
        return decoder.decode(raw, final=not truncated)
    except UnicodeDecodeError as exception:
        raise ValidationError("CSV preview bytes are not valid UTF-8") from exception
