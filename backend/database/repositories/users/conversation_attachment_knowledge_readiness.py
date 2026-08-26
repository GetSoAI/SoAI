"""SoAI - Knowledge attachment readiness predicates [backend/database/repositories/users/conversation_attachment_knowledge_readiness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.epoch import EPOCH_MS_MIN
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "knowledge_attachment_completed_count_sql",
    "knowledge_attachment_has_completed_items",
    "knowledge_attachment_has_finalized_timestamp",
    "knowledge_attachment_processing_state_ready",
    "knowledge_attachment_ready_for_reference_params",
    "knowledge_attachment_ready_for_reference_sql",
    "knowledge_attachment_summary_ready_for_reference_sql",
)

_READY_PROCESSING_STATE = "ready"
_READY_PROCESSING_STATE_PARAMS: tuple[str, ...] = (_READY_PROCESSING_STATE,)
_ACTIVE_ITEM_STATUS_PARAMS: tuple[str, ...] = (
    "chunking",
    "embedding",
    "fetching",
    "parsing",
    "queued",
)


def _knowledge_readiness_placeholders(values: tuple[str, ...]) -> str:
    return ",".join("?" for _ in values)


def knowledge_attachment_completed_count_sql(summary_reference: str) -> str:
    return f"COALESCE(CAST(json_extract({summary_reference}.status_counts_json, '$.completed') AS INTEGER), 0)"


def _knowledge_attachment_ready_for_reference_sql(summary_reference: str) -> str:
    return f"""
          AND {summary_reference}.processing_state IN ({_knowledge_readiness_placeholders(_READY_PROCESSING_STATE_PARAMS)})
          AND {summary_reference}.finalized_at_ms IS NOT NULL
          AND {knowledge_attachment_completed_count_sql(summary_reference)} > 0
          AND NOT EXISTS (
              SELECT 1
              FROM webui_conversation_knowledge_attachment_items i
              WHERE i.conv_id = {summary_reference}.conv_id
                AND i.user_id = {summary_reference}.user_id
                AND i.knowledge_attachment_id = {summary_reference}.id
                AND (
                    i.rag_status IS NULL
                    OR i.rag_status IN ({_knowledge_readiness_placeholders(_ACTIVE_ITEM_STATUS_PARAMS)})
                )
              LIMIT 1
          )
    """


def knowledge_attachment_ready_for_reference_sql() -> str:
    return _knowledge_attachment_ready_for_reference_sql("webui_conversation_knowledge_attachments")


def knowledge_attachment_summary_ready_for_reference_sql() -> str:
    return _knowledge_attachment_ready_for_reference_sql("summary")


def knowledge_attachment_has_finalized_timestamp(row: JSONDict) -> bool:
    finalized_at_ms = row.get("finalized_at_ms")
    return (
        isinstance(finalized_at_ms, int)
        and not isinstance(finalized_at_ms, bool)
        and finalized_at_ms >= EPOCH_MS_MIN
    )


def knowledge_attachment_has_completed_items(row: JSONDict) -> bool:
    status_counts = row.get("status_counts")
    if not isinstance(status_counts, dict):
        return False
    completed = status_counts.get("completed")
    return is_strict_int(completed) and completed > 0


def knowledge_attachment_processing_state_ready(value: JSONValue) -> bool:
    return value == _READY_PROCESSING_STATE


def knowledge_attachment_ready_for_reference_params() -> tuple[str, ...]:
    return (*_READY_PROCESSING_STATE_PARAMS, *_ACTIVE_ITEM_STATUS_PARAMS)
