"""SoAI - PDF document merge helpers [backend/core/browser/pdf_document_merge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io

from pypdfium2 import PdfDocument

from core.errors.exceptions import ValidationError
from core.filesystem.atomic_binary_writes import atomic_write_binary

__all__ = ("merge_pdf_documents",)


def merge_pdf_documents(*, cover_pdf: bytes, body_pdf: bytes, output_path: str) -> None:
    if not cover_pdf.startswith(b"%PDF"):
        raise ValidationError("Cover render did not produce a PDF.")
    if not body_pdf.startswith(b"%PDF"):
        raise ValidationError("Conversation render did not produce a PDF.")
    with (
        PdfDocument.new() as merged,
        PdfDocument(cover_pdf) as cover,
        PdfDocument(body_pdf) as body,
    ):
        merged.import_pages(cover)
        merged.import_pages(body)

        def write_merged_document(handle: io.BufferedIOBase) -> None:
            merged.save(handle)

        atomic_write_binary(output_path, write_merged_document)
