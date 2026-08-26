"""SoAI - RAG document status update queries [backend/database/repositories/files/rag_document_status_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import DatabaseError
from core.rag.job_operations import rag_job_lease_lost_details
from core.timing.epoch import epoch_ms
from database.core.sql_builders import build_update_statement
from database.repositories.files.rag_linked_document_refresh import (
    sync_refresh_linked_knowledge_for_source_documents,
)
from database.repositories.users.conversation_attachment_knowledge_status import (
    sync_update_knowledge_attachment_item_status_for_document,
)

if TYPE_CHECKING:
    from core.rag.job_operations import (
        RAGDocumentStatusJobUpdateRequest,
        RAGDocumentStatusUpdateRequest,
    )
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "sync_update_rag_document_status",
    "sync_update_rag_document_status_for_job",
)

_ALLOWED_RAG_DOCUMENT_STATUS_UPDATE_COLS = frozenset(
    (
        "status",
        "status_details",
        "content_hash",
        "total_chunks",
        "processed_chunks",
        "embedding_model",
        "effective_embedding_model",
        "embedding_dimensions",
        "error_message",
        "processing_started_at_ms",
        "processing_completed_at_ms",
    ),
)
_TERMINAL_RAG_DOCUMENT_STATUSES: tuple[str, ...] = ("completed", "error", "cancelled")


def _terminal_status_placeholders() -> str:
    return ",".join("?" for _ in _TERMINAL_RAG_DOCUMENT_STATUSES)


def _status_where(status: str) -> tuple[str, tuple[str, ...]]:
    where_clause = (
        "id = ? AND " f"(status = ? OR status NOT IN ({_terminal_status_placeholders()}))"
    )
    return where_clause, (status, *_TERMINAL_RAG_DOCUMENT_STATUSES)


def _build_updates(
    *,
    status: str,
    now: int,
    status_details: str | None,
    content_hash: str | None,
    total_chunks: int | None,
    processed_chunks: int | None,
    embedding_model: str | None,
    effective_embedding_model: str | None,
    embedding_dimensions: int | None,
    error_message: str | None,
) -> dict[str, SQLiteValue]:
    updates: dict[str, SQLiteValue] = {"status": status}
    if status == "parsing":
        updates["processing_started_at_ms"] = now
    elif status in _TERMINAL_RAG_DOCUMENT_STATUSES:
        updates["processing_completed_at_ms"] = now
    optional_updates: tuple[tuple[str, SQLiteValue | None], ...] = (
        ("status_details", status_details),
        ("content_hash", content_hash),
        ("total_chunks", total_chunks),
        ("processed_chunks", processed_chunks),
        ("embedding_model", embedding_model),
        ("effective_embedding_model", effective_embedding_model),
        ("embedding_dimensions", embedding_dimensions),
        ("error_message", error_message),
    )
    for column, value in optional_updates:
        if value is not None:
            updates[column] = value
    return updates


def _apply_side_effects(
    conn: sqlite3.Connection,
    *,
    doc_id: str,
    status: str,
    error_message: str | None,
    updated_at_ms: int,
) -> tuple[list[JSONDict], JSONDict | None]:
    linked_summaries = sync_refresh_linked_knowledge_for_source_documents(
        conn,
        source_document_ids=(doc_id,),
        updated_at_ms=updated_at_ms,
    )
    knowledge_summary = sync_update_knowledge_attachment_item_status_for_document(
        conn,
        document_id=doc_id,
        rag_status=status,
        error_message=error_message,
        updated_at_ms=updated_at_ms,
    )
    return linked_summaries, knowledge_summary


def _execute_status_update(
    conn: sqlite3.Connection,
    *,
    doc_id: str,
    updates: dict[str, SQLiteValue],
    where_clause: str,
    where_params: tuple[SQLiteValue, ...],
) -> bool:
    sql, params = build_update_statement(
        table="rag_documents",
        updates=updates,
        where_clause=where_clause,
        where_params=(doc_id, *where_params),
        allowed_columns=set(_ALLOWED_RAG_DOCUMENT_STATUS_UPDATE_COLS),
    )
    cursor = conn.execute(sql, params)
    return cursor.rowcount > 0


def _build_updates_from_request(
    request: RAGDocumentStatusUpdateRequest,
    *,
    now: int,
) -> dict[str, SQLiteValue]:
    return _build_updates(
        status=request.status,
        now=now,
        status_details=request.status_details,
        content_hash=request.content_hash,
        total_chunks=request.total_chunks,
        processed_chunks=request.processed_chunks,
        embedding_model=request.embedding_model,
        effective_embedding_model=request.effective_embedding_model,
        embedding_dimensions=request.embedding_dimensions,
        error_message=request.error_message,
    )


def sync_update_rag_document_status(
    conn: sqlite3.Connection,
    request: RAGDocumentStatusUpdateRequest,
) -> tuple[list[JSONDict], JSONDict | None]:
    now = epoch_ms()
    updates = _build_updates_from_request(request, now=now)
    where_clause, status_where_params = _status_where(request.status)
    if _execute_status_update(
        conn,
        doc_id=request.doc_id,
        updates=updates,
        where_clause=where_clause,
        where_params=status_where_params,
    ):
        return _apply_side_effects(
            conn,
            doc_id=request.doc_id,
            status=request.status,
            error_message=request.error_message,
            updated_at_ms=now,
        )
    return [], None


def sync_update_rag_document_status_for_job(
    conn: sqlite3.Connection,
    request: RAGDocumentStatusJobUpdateRequest,
) -> tuple[list[JSONDict], JSONDict | None]:
    now = epoch_ms()
    status_update = request.status_update
    updates = _build_updates_from_request(status_update, now=now)
    status_where_clause, status_where_params = _status_where(status_update.status)
    where_clause = (
        f"{status_where_clause} "
        "AND EXISTS ("
        "SELECT 1 FROM rag_processing_jobs "
        "WHERE job_id = ? AND document_id = rag_documents.id "
        "AND lease_token = ? AND status = 'running' "
        "AND lease_expires_at_ms IS NOT NULL AND lease_expires_at_ms >= ?"
        ")"
    )
    where_params: tuple[SQLiteValue, ...] = (
        *status_where_params,
        request.job_id,
        request.lease_token,
        now,
    )
    if _execute_status_update(
        conn,
        doc_id=status_update.doc_id,
        updates=updates,
        where_clause=where_clause,
        where_params=where_params,
    ):
        return _apply_side_effects(
            conn,
            doc_id=status_update.doc_id,
            status=status_update.status,
            error_message=status_update.error_message,
            updated_at_ms=now,
        )
    raise DatabaseError(
        "RAG document update lost its processing job lease.",
        details=rag_job_lease_lost_details(),
    )
