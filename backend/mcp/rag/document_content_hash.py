"""SoAI - Stable hashing for RAG document content [backend/mcp/rag/document_content_hash.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib

__all__ = ("compute_document_content_hash",)


def compute_document_content_hash(text: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()
