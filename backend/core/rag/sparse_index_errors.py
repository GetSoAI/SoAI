"""SoAI - Sparse index readiness errors [backend/core/rag/sparse_index_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError

__all__ = ("SparseIndexRebuildRequiredError",)


class SparseIndexRebuildRequiredError(StateError): ...
