"""SoAI - Document OCR result contracts [backend/files/parsers/document_ocr_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = ("DocumentOcrOutcome", "DocumentOcrResult", "RasterCandidate")


class DocumentOcrOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class RasterCandidate:
    label: str
    path: str


@dataclass(frozen=True, slots=True)
class DocumentOcrResult:
    outcome: DocumentOcrOutcome
    supplements: tuple[str, ...] = ()
    page_count: int | None = None
    complete: bool = True
