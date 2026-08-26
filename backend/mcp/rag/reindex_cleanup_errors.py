"""SoAI - MCP RAG reindex cleanup exception groups [backend/mcp/rag/reindex_cleanup_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import SoAIError

__all__ = ("REINDEX_CLEANUP_EXCEPTIONS",)

REINDEX_CLEANUP_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    RuntimeError,
    OSError,
    TypeError,
    ValueError,
)
