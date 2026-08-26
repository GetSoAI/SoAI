"""SoAI - Document type detection helpers [backend/core/files/document_type_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.files.content_types import normalize_content_type
from core.files.image_candidates import is_supported_image_candidate
from core.files.mime_detection import detect_mime_type
from core.filesystem.open_files import open_binary

__all__ = (
    "detect_mime_from_path",
    "extract_extension",
    "is_image_type",
    "is_pdf_type",
)

_MIME_SAMPLE_BYTES: int = 8192


def extract_extension(file_path: str) -> str:
    _, extension = os.path.splitext(str(file_path or ""))
    if extension.startswith("."):
        return extension[1:].strip().lower()
    return extension.strip().lower()


def detect_mime_from_path(file_path: str) -> str:
    try:
        with open_binary(file_path, mode="rb") as handle:
            sample = handle.read(_MIME_SAMPLE_BYTES)
    except OSError:
        sample = b""
    return (detect_mime_type(sample, filename=os.path.basename(file_path)) or "").strip()


def is_pdf_type(detected_mime: str, extension: str) -> bool:
    if extension == "pdf":
        return True
    return normalize_content_type(detected_mime) == "application/pdf"


def is_image_type(detected_mime: str, extension: str) -> bool:
    return is_supported_image_candidate(path=f"candidate.{extension}", content_type=detected_mime)
