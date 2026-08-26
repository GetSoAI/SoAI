"""SoAI - RAG Knowledge prompt row parsing [backend/database/repositories/rag_knowledge_prompt_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError
from core.rag.knowledge_prompt_types import (
    KnowledgePromptDeliveryRecord,
    KnowledgePromptEventRecord,
)
from database.core.json_codec import (
    safe_json_deserialize_required_list,
    safe_json_deserialize_required_object,
)
from database.core.sqlite_numbers import coerce_non_negative_int_from_sqlite_numberish
from database.core.sqlite_row_scalars import (
    require_sqlite_row_trimmed_non_empty_str,
    sqlite_row_optional_trimmed_str,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRow

__all__ = (
    "parse_knowledge_prompt_delivery_record",
    "parse_knowledge_prompt_event_record",
    "require_knowledge_prompt_event_type",
)


def require_knowledge_prompt_event_type(
    value: str,
) -> Literal[
    "documents_added",
    "documents_removed",
    "document_processing_completed",
    "document_processing_failed",
    "document_processing_cancelled",
    "knowledge_reindex_queued",
    "knowledge_reindex_completed",
    "knowledge_reindex_failed",
    "knowledge_reindex_cancelled",
]:
    if value == "documents_added":
        return "documents_added"
    if value == "documents_removed":
        return "documents_removed"
    if value == "document_processing_completed":
        return "document_processing_completed"
    if value == "document_processing_failed":
        return "document_processing_failed"
    if value == "document_processing_cancelled":
        return "document_processing_cancelled"
    if value == "knowledge_reindex_queued":
        return "knowledge_reindex_queued"
    if value == "knowledge_reindex_completed":
        return "knowledge_reindex_completed"
    if value == "knowledge_reindex_failed":
        return "knowledge_reindex_failed"
    if value == "knowledge_reindex_cancelled":
        return "knowledge_reindex_cancelled"
    raise StateError("Knowledge prompt event type is invalid.")


def _read_required_str(row: SQLiteRow, key: str) -> str:
    return require_sqlite_row_trimmed_non_empty_str(row, key, label="Knowledge prompt row")


def _read_optional_str(row: SQLiteRow, key: str) -> str | None:
    return sqlite_row_optional_trimmed_str(row, key, label="Knowledge prompt row")


def _read_optional_int(row: SQLiteRow, key: str) -> int | None:
    value = row.get(key)
    if value is None:
        return None
    return coerce_non_negative_int_from_sqlite_numberish(value)


def parse_knowledge_prompt_event_record(row: SQLiteRow) -> KnowledgePromptEventRecord:
    event_type = require_knowledge_prompt_event_type(_read_required_str(row, "event_type"))
    raw_names = safe_json_deserialize_required_list(
        row.get("document_names_json"),
        error_message="Knowledge prompt event document names are invalid.",
    )
    document_names: list[str] = []
    for item in raw_names:
        if isinstance(item, str):
            normalized = item.strip()
            if normalized:
                document_names.append(normalized)
    details = safe_json_deserialize_required_object(
        row.get("details_json"),
        error_message="Knowledge prompt event details are invalid.",
    )
    return KnowledgePromptEventRecord(
        id=coerce_non_negative_int_from_sqlite_numberish(row.get("id")),
        conv_id=_read_required_str(row, "conv_id"),
        user_id=coerce_non_negative_int_from_sqlite_numberish(row.get("user_id")),
        event_type=event_type,
        document_names=tuple(document_names),
        document_count=coerce_non_negative_int_from_sqlite_numberish(row.get("document_count")),
        details=details,
        created_at_ms=coerce_non_negative_int_from_sqlite_numberish(row.get("created_at_ms")),
    )


def parse_knowledge_prompt_delivery_record(row: SQLiteRow) -> KnowledgePromptDeliveryRecord:
    return KnowledgePromptDeliveryRecord(
        conv_id=_read_required_str(row, "conv_id"),
        user_id=coerce_non_negative_int_from_sqlite_numberish(row.get("user_id")),
        last_delivered_event_id=coerce_non_negative_int_from_sqlite_numberish(
            row.get("last_delivered_event_id"),
        ),
        last_delivered_state_signature=_read_optional_str(row, "last_delivered_state_signature"),
        active_claim_id=_read_optional_str(row, "active_claim_id"),
        active_claim_request_id=_read_optional_str(row, "active_claim_request_id"),
        active_claim_event_ceiling_id=_read_optional_int(row, "active_claim_event_ceiling_id"),
        active_claim_state_signature=_read_optional_str(row, "active_claim_state_signature"),
        active_claim_expires_at_ms=_read_optional_int(row, "active_claim_expires_at_ms"),
        last_delivered_at_ms=_read_optional_int(row, "last_delivered_at_ms"),
    )
