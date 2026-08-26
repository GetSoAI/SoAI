"""SoAI - MCP read_file content classification [backend/mcp/tools/file_content_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.files.content_types import content_type_is_text
from core.files.mime_detection import detect_mime_type
from core.filesystem.open_files import open_binary

__all__ = (
    "FileReadContentClassification",
    "classify_read_file_content",
    "classify_read_file_sample",
)

_SAMPLE_BYTES = 8192


@dataclass(frozen=True, slots=True)
class FileReadContentClassification:
    mime_type: str
    size_bytes: int
    text_safe: bool


def classify_read_file_content(
    path: str,
    data: bytes | None = None,
) -> FileReadContentClassification:
    if data is None:
        try:
            size_bytes = os.path.getsize(path)
            with open_binary(path, mode="rb") as file_handle:
                sample = file_handle.read(_SAMPLE_BYTES)
        except OSError as exception:
            raise ValidationError(f"Unable to inspect file content: {path}") from exception
    else:
        size_bytes = len(data)
        sample = data[:_SAMPLE_BYTES]
    return classify_read_file_sample(path=path, sample=sample, size_bytes=size_bytes)


def classify_read_file_sample(
    *,
    path: str,
    sample: bytes,
    size_bytes: int,
) -> FileReadContentClassification:
    if not sample:
        return FileReadContentClassification(
            mime_type="text/plain",
            size_bytes=size_bytes,
            text_safe=True,
        )
    detected_mime = (detect_mime_type(sample, filename=path) or "").strip()
    if detected_mime:
        return FileReadContentClassification(
            mime_type=detected_mime,
            size_bytes=size_bytes,
            text_safe=content_type_is_text(detected_mime),
        )
    return FileReadContentClassification(
        mime_type="application/octet-stream",
        size_bytes=size_bytes,
        text_safe=False,
    )
