"""SoAI - Content-based MIME refinement for extensionless files [backend/features/file_explorer/mime_content_refine.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.files.mime_detection import detect_mime_type

__all__ = (
    "MIME_CONTENT_SAMPLE_BYTES",
    "OCTET_STREAM_CONTENT_TYPE",
    "refine_octet_stream_mime",
)

MIME_CONTENT_SAMPLE_BYTES: int = 8192
OCTET_STREAM_CONTENT_TYPE: str = "application/octet-stream"


def refine_octet_stream_mime(name: str, mime: str, sample: bytes) -> str:
    if mime != OCTET_STREAM_CONTENT_TYPE or not sample:
        return mime
    sniffed = detect_mime_type(sample, filename=name)
    if sniffed is None:
        return mime
    return sniffed
