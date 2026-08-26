"""SoAI - Document text slicing and readability [backend/files/parsers/document_text_slicing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.extraction_state import ExtractionState
from core.files.types import DocumentReadResult
from core.text.chunked_reads import slice_chunked_text

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "is_extraction_readable",
    "slice_document_text",
)


def is_extraction_readable(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    compact = "".join(ch for ch in normalized if not ch.isspace())
    if len(compact) < 40:
        return False
    replacement_count = compact.count("\ufffd")
    if replacement_count > 0 and replacement_count / max(len(compact), 1) > 0.02:
        return False
    letters_or_digits = sum(1 for ch in compact if ch.isalpha() or ch.isdigit())
    return (letters_or_digits / max(len(compact), 1)) >= 0.15


def slice_document_text(
    *,
    content: str,
    parser_used: str,
    detected_type: str,
    page_count: int | None,
    metadata: JSONDict | None,
    warnings: tuple[str, ...],
    max_chars: int,
    offset_chars: int,
    extraction_state: ExtractionState,
) -> DocumentReadResult:
    chunked = slice_chunked_text(
        content=content,
        max_chars=max_chars,
        offset_chars=offset_chars,
        content_complete=True,
    )
    return DocumentReadResult(
        content=chunked.content,
        parser_used=parser_used,
        detected_type=detected_type,
        page_count=page_count,
        metadata=metadata,
        truncated=chunked.truncated,
        warnings=tuple(list(warnings) + list(chunked.warnings)),
        offset_chars=chunked.offset_chars,
        next_offset_chars=chunked.next_offset_chars,
        total_chars=chunked.total_chars,
        extraction_state=(
            ExtractionState.DEGRADED
            if chunked.truncated and extraction_state is ExtractionState.COMPLETE
            else extraction_state
        ),
    )
