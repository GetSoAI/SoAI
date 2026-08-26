"""SoAI - Document response detection helpers [backend/mcp/handlers/tools/document_response_detection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.files.content_types import content_type_is_document
from mcp.rag.scraper.parsing import extension_from_url

__all__ = (
    "is_probable_document_response",
    "is_probable_document_url",
)

_DOCUMENT_EXTENSIONS: frozenset[str] = frozenset(
    {
        "pdf",
        "doc",
        "docx",
        "ppt",
        "pptx",
        "xls",
        "xlsx",
        "odt",
        "odp",
        "ods",
        "rtf",
        "epub",
    },
)


def is_probable_document_url(url: str) -> bool:
    extension = extension_from_url(url)
    return bool(extension) and extension in _DOCUMENT_EXTENSIONS


def is_probable_document_response(*, final_url: str, content_type: str | None) -> bool:
    if content_type_is_document(content_type):
        return True
    return is_probable_document_url(final_url)
