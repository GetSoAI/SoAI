"""SoAI - WebUI knowledge attachment status values [backend/core/attachments/knowledge_attachment_statuses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "KNOWLEDGE_ACTIVE_ITEM_STATUSES",
    "KNOWLEDGE_ACTIVE_PROCESSING_STATES",
    "KNOWLEDGE_ITEM_STATUSES",
    "KNOWLEDGE_OPERATION_TYPES",
    "KNOWLEDGE_SOURCE_TYPES",
    "KNOWLEDGE_TERMINAL_ITEM_STATUSES",
    "KNOWLEDGE_TERMINAL_PROCESSING_STATES",
    "RAG_DOCUMENT_STATUS_COUNT_KEYS",
)

KNOWLEDGE_ITEM_STATUSES: frozenset[str] = frozenset(
    (
        "queued",
        "fetching",
        "parsing",
        "chunking",
        "embedding",
        "completed",
        "error",
        "cancelled",
        "skipped",
    ),
)
KNOWLEDGE_ACTIVE_ITEM_STATUSES: frozenset[str] = frozenset(
    ("queued", "fetching", "parsing", "chunking", "embedding"),
)
KNOWLEDGE_TERMINAL_ITEM_STATUSES: frozenset[str] = frozenset(
    ("completed", "error", "cancelled", "skipped"),
)
KNOWLEDGE_ACTIVE_PROCESSING_STATES: frozenset[str] = frozenset(("pending", "running", "cancelling"))
KNOWLEDGE_TERMINAL_PROCESSING_STATES: frozenset[str] = frozenset(("ready", "error", "cancelled"))
RAG_DOCUMENT_STATUS_COUNT_KEYS: tuple[str, ...] = (
    "queued",
    "fetching",
    "parsing",
    "chunking",
    "embedding",
    "completed",
    "error",
)
_KNOWLEDGE_UPLOAD_SOURCE_TYPES: tuple[str, ...] = (
    "composer_document_upload",
    "composer_folder_upload",
    "knowledge_tab_document_upload",
    "knowledge_tab_folder_upload",
)
_KNOWLEDGE_MAINTENANCE_SOURCE_TYPES: tuple[str, ...] = (
    "file_explorer_folder_import",
    "document_delete",
    "bulk_delete",
    "reindex",
)
_KNOWLEDGE_REFERENCE_SOURCE_TYPES: tuple[str, ...] = ("linked_knowledge",)
KNOWLEDGE_SOURCE_TYPES: frozenset[str] = frozenset(
    (
        *_KNOWLEDGE_UPLOAD_SOURCE_TYPES,
        *_KNOWLEDGE_MAINTENANCE_SOURCE_TYPES,
        *_KNOWLEDGE_REFERENCE_SOURCE_TYPES,
    ),
)
KNOWLEDGE_OPERATION_TYPES: frozenset[str] = frozenset(("added", "removed", "updated", "reindexed"))
