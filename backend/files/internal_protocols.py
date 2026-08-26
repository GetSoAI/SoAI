"""SoAI - Internal file subsystem protocols [backend/files/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.files.types import ParsedDocument, ParseExecutionContext
from files.parsers.document_ocr_types import DocumentOcrResult

__all__ = ("DocumentOcrCoordinatorProtocol",)


class DocumentOcrCoordinatorProtocol(Protocol):
    async def supplement(
        self,
        *,
        context: ParseExecutionContext,
        tika_document: ParsedDocument,
        extension: str,
        needed_chars: int,
    ) -> DocumentOcrResult: ...
