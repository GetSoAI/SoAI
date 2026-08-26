"""SoAI - Durable RAG job row parsing [backend/database/repositories/files/rag_job_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.database_types import RAGProcessingJobRecord
from database.core.json_codec import safe_json_deserialize
from database.core.sqlite_numbers import (
    coerce_optional_int_from_sqlite_row,
    coerce_optional_str_from_sqlite_row,
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRow

__all__ = (
    "RAG_PROCESSING_JOB_COLUMNS",
    "parse_rag_processing_job_row",
)

RAG_PROCESSING_JOB_COLUMNS = (
    "job_id, job_type, conv_id, user_id, document_id, task_id, status, payload_json, "
    "spool_path, lease_token, lease_owner, lease_expires_at_ms, attempt_count, "
    "last_error, created_at_ms, updated_at_ms, completed_at_ms"
)


def parse_rag_processing_job_row(row: SQLiteRow) -> RAGProcessingJobRecord:
    return {
        "job_id": coerce_required_nonempty_str_from_sqlite_row(row, "job_id"),
        "job_type": coerce_required_nonempty_str_from_sqlite_row(row, "job_type"),
        "conv_id": coerce_required_nonempty_str_from_sqlite_row(row, "conv_id"),
        "user_id": coerce_required_int_from_sqlite_row(row, "user_id"),
        "document_id": coerce_optional_str_from_sqlite_row(row, "document_id"),
        "task_id": coerce_required_nonempty_str_from_sqlite_row(row, "task_id"),
        "status": coerce_required_nonempty_str_from_sqlite_row(row, "status"),
        "payload": safe_json_deserialize(row.get("payload_json"), {}),
        "spool_path": coerce_optional_str_from_sqlite_row(row, "spool_path"),
        "lease_token": coerce_optional_str_from_sqlite_row(row, "lease_token"),
        "lease_owner": coerce_optional_str_from_sqlite_row(row, "lease_owner"),
        "lease_expires_at_ms": coerce_optional_int_from_sqlite_row(row, "lease_expires_at_ms"),
        "attempt_count": coerce_required_int_from_sqlite_row(row, "attempt_count"),
        "last_error": coerce_optional_str_from_sqlite_row(row, "last_error"),
        "created_at_ms": coerce_required_int_from_sqlite_row(row, "created_at_ms"),
        "updated_at_ms": coerce_required_int_from_sqlite_row(row, "updated_at_ms"),
        "completed_at_ms": coerce_optional_int_from_sqlite_row(row, "completed_at_ms"),
    }
