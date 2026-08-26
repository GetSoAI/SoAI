"""SoAI - Shared chunked text read helpers [backend/core/text/chunked_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "ChunkedTextRead",
    "slice_chunked_text",
)


@dataclass(frozen=True, slots=True)
class ChunkedTextRead:
    content: str
    truncated: bool
    warnings: tuple[str, ...]
    offset_chars: int
    next_offset_chars: int | None
    total_chars: int | None


def slice_chunked_text(
    *,
    content: str,
    max_chars: int,
    offset_chars: int,
    content_complete: bool,
) -> ChunkedTextRead:
    normalized = str(content or "")
    requested_offset = max(offset_chars, 0)
    start = min(requested_offset, len(normalized))
    end = min(start + max_chars, len(normalized))
    sliced = normalized[start:end]
    offset_beyond_end = requested_offset > len(normalized)
    extracted_has_more = end < len(normalized)
    may_have_more = extracted_has_more or not content_complete
    if not may_have_more or offset_beyond_end:
        next_offset = None
    else:
        next_offset = end
    warning_list: list[str] = []
    if offset_beyond_end:
        warning_list.append(
            f"offset_chars={requested_offset} is beyond extracted text length ({len(normalized)} chars).",
        )
    if may_have_more and offset_beyond_end:
        warning_list.append(
            f"Extraction incomplete at requested offset. Retry with offset_chars={requested_offset}.",
        )
    elif may_have_more:
        warning_list.append(
            f"Content truncated to {max_chars} chars. Continue with offset_chars={next_offset}.",
        )
    return ChunkedTextRead(
        content=sliced,
        truncated=may_have_more,
        warnings=tuple(warning_list),
        offset_chars=offset_chars,
        next_offset_chars=next_offset,
        total_chars=len(normalized) if content_complete else None,
    )
