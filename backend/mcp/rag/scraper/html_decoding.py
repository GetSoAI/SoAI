"""SoAI - HTML byte decoding utilities for scraper [backend/mcp/rag/scraper/html_decoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from charset_normalizer import from_bytes

from mcp.rag.scraper.internal_protocols import CharsetDetectorProtocol

__all__ = ("decode_bytes_to_text",)


def decode_bytes_to_text(
    data: bytes,
    *,
    charset_hint: str | None = None,
    detector: CharsetDetectorProtocol | None = None,
) -> str:
    if charset_hint:
        try:
            return data.decode(charset_hint)
        except (LookupError, UnicodeDecodeError):
            charset_hint = None
    if detector is None:
        detector = from_bytes
    detection_result = detector(data)
    best = detection_result.best()
    if best:
        decoded = str(best)
        if decoded:
            return decoded
    return data.decode("utf-8", errors="replace")
