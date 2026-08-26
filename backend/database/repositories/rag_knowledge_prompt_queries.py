"""SoAI - RAG Knowledge prompt queries [backend/database/repositories/rag_knowledge_prompt_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.rag.knowledge_prompt_types import (
    KnowledgePromptDeliveryRecord,
    KnowledgePromptEventRecord,
    KnowledgePromptProjectionInputs,
)
from core.types.json import JSONDict
from database.core.query_execution import query_to_dicts
from database.repositories.rag_knowledge_prompt_records import (
    parse_knowledge_prompt_delivery_record,
    parse_knowledge_prompt_event_record,
)

__all__ = (
    "load_prompt_projection_inputs_query",
    "read_pending_events_after_query",
)


async def _load_delivery(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> KnowledgePromptDeliveryRecord | None:
    rows = await query_to_dicts(
        database,
        """SELECT conv_id, user_id, last_delivered_event_id, last_delivered_state_signature,
                  active_claim_id, active_claim_request_id, active_claim_event_ceiling_id,
                  active_claim_state_signature, active_claim_expires_at_ms, last_delivered_at_ms
           FROM rag_knowledge_prompt_delivery
           WHERE conv_id = ? AND user_id = ?""",
        (conv_id, user_id),
    )
    if not rows:
        return None
    return parse_knowledge_prompt_delivery_record(rows[0])


async def read_pending_events_after_query(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
    last_delivered_event_id: int,
    max_events: int,
) -> tuple[KnowledgePromptEventRecord, ...]:
    rows = await query_to_dicts(
        database,
        """SELECT id, conv_id, user_id, event_type, document_names_json, document_count,
                  details_json, created_at_ms
           FROM rag_knowledge_prompt_events
           WHERE conv_id = ? AND user_id = ? AND id > ?
           ORDER BY id DESC
           LIMIT ?""",
        (conv_id, user_id, max(0, int(last_delivered_event_id)), max(0, int(max_events))),
    )
    return tuple(parse_knowledge_prompt_event_record(row) for row in rows)


async def _load_rag_config(database: aiosqlite.Connection, conv_id: str) -> JSONDict | None:
    rows = await query_to_dicts(
        database,
        """SELECT enabled, retrieval_strategy, top_k, similarity_threshold, chunking_strategy,
                  chunk_size, chunk_overlap, embedding_model
           FROM rag_conversation_config
           WHERE conv_id = ?""",
        (conv_id,),
    )
    if not rows:
        return None
    row = rows[0]
    embedding_model = row.get("embedding_model")
    return {
        "enabled": row.get("enabled") == 1,
        "retrieval_strategy": str(row.get("retrieval_strategy") or ""),
        "top_k": int(row.get("top_k") or 0),
        "similarity_threshold": float(row.get("similarity_threshold") or 0.0),
        "chunking_strategy": str(row.get("chunking_strategy") or ""),
        "chunk_size": int(row.get("chunk_size") or 0),
        "chunk_overlap": int(row.get("chunk_overlap") or 0),
        "embedding_model": embedding_model if isinstance(embedding_model, str) else None,
    }


async def _load_rag_counts(database: aiosqlite.Connection, conv_id: str) -> JSONDict:
    rows = await query_to_dicts(
        database,
        """SELECT
             COUNT(*) AS document_count,
             SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) AS queued,
             SUM(CASE WHEN status = 'fetching' THEN 1 ELSE 0 END) AS fetching,
             SUM(CASE WHEN status = 'parsing' THEN 1 ELSE 0 END) AS parsing,
             SUM(CASE WHEN status = 'chunking' THEN 1 ELSE 0 END) AS chunking,
             SUM(CASE WHEN status = 'embedding' THEN 1 ELSE 0 END) AS embedding,
             SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
             SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error,
             (SELECT COUNT(*) FROM rag_chunks c JOIN rag_documents d ON c.document_id = d.id
              WHERE d.conv_id = ?) AS chunk_count
           FROM rag_documents WHERE conv_id = ?""",
        (conv_id, conv_id),
    )
    row = rows[0] if rows else {}
    return {
        key: int(row.get(key) or 0)
        for key in (
            "document_count",
            "queued",
            "fetching",
            "parsing",
            "chunking",
            "embedding",
            "completed",
            "error",
            "chunk_count",
        )
    }


async def _load_latest_documents(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    max_documents: int,
) -> tuple[JSONDict, ...]:
    rows = await query_to_dicts(
        database,
        """SELECT id, filename, status, total_chunks, processed_chunks, error_message, created_at_ms
           FROM rag_documents
           WHERE conv_id = ?
           ORDER BY created_at_ms DESC
           LIMIT ?""",
        (conv_id, max(0, int(max_documents))),
    )
    return tuple(dict(row) for row in rows)


async def load_prompt_projection_inputs_query(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
    max_pending_events: int,
    max_documents: int,
) -> KnowledgePromptProjectionInputs:
    delivery = await _load_delivery(database, conv_id=conv_id, user_id=user_id)
    last_delivered_event_id = delivery.last_delivered_event_id if delivery is not None else 0
    return KnowledgePromptProjectionInputs(
        delivery=delivery,
        pending_events=await read_pending_events_after_query(
            database,
            conv_id=conv_id,
            user_id=user_id,
            last_delivered_event_id=last_delivered_event_id,
            max_events=max_pending_events,
        ),
        rag_config=await _load_rag_config(database, conv_id),
        rag_counts=await _load_rag_counts(database, conv_id),
        latest_documents=await _load_latest_documents(
            database,
            conv_id=conv_id,
            max_documents=max_documents,
        ),
    )
