"""SoAI - Linked knowledge selection SQL and validation [backend/database/repositories/users/conversation_linked_knowledge_selection_core.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError
from database.repositories.users.conversation_attachment_knowledge_readiness import (
    knowledge_attachment_ready_for_reference_params,
    knowledge_attachment_summary_ready_for_reference_sql,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ensure_linked_knowledge_items_complete",
    "linked_knowledge_active_client_batch_query",
    "linked_knowledge_batch_links_query",
    "linked_knowledge_canonical_items_params",
    "linked_knowledge_canonical_items_query",
    "linked_knowledge_catalog_source_exists_sql",
    "linked_knowledge_item_placeholders",
    "linked_knowledge_request_matches_existing",
    "linked_knowledge_selection_matches_existing",
    "linked_knowledge_source_operation_params",
    "linked_knowledge_source_operation_sql",
)

LINKED_KNOWLEDGE_SELECTION_FIELDS = (
    "source_conv_id",
    "source_user_id",
    "source_knowledge_attachment_id",
    "source_item_id",
    "source_document_id",
)
_LINKED_KNOWLEDGE_SOURCE_OPERATION_PARAMS: tuple[str, ...] = ("added", "reindexed", "updated")


def _linked_knowledge_source_operation_placeholders() -> str:
    return ",".join("?" for _ in _LINKED_KNOWLEDGE_SOURCE_OPERATION_PARAMS)


def linked_knowledge_item_placeholders(item_ids: tuple[int, ...]) -> str:
    if not item_ids:
        raise ConflictError("Linked knowledge selection is required.")
    return ",".join("?" for _ in item_ids)


def linked_knowledge_source_operation_sql(summary_reference: str) -> str:
    return (
        f"AND {summary_reference}.operation_type "
        f"IN ({_linked_knowledge_source_operation_placeholders()})"
    )


def linked_knowledge_source_operation_params() -> tuple[str, ...]:
    return _LINKED_KNOWLEDGE_SOURCE_OPERATION_PARAMS


def linked_knowledge_catalog_source_exists_sql() -> str:
    return f"""
      AND EXISTS (
          SELECT 1
          FROM webui_conversation_knowledge_attachment_items item
          JOIN rag_documents document
            ON document.id = item.document_id
           AND document.conv_id = item.conv_id
           AND document.user_id = item.user_id
          WHERE item.conv_id = webui_conversation_knowledge_attachments.conv_id
            AND item.user_id = webui_conversation_knowledge_attachments.user_id
            AND item.knowledge_attachment_id = webui_conversation_knowledge_attachments.id
            {linked_knowledge_source_operation_sql("item")}
            AND item.rag_status = 'completed'
            AND document.status = 'completed'
          LIMIT 1
      )
    """


def linked_knowledge_canonical_items_query(*, item_placeholders: str) -> str:
    return f"""
        SELECT
            item.conv_id AS source_conv_id,
            item.user_id AS source_user_id,
            item.knowledge_attachment_id AS source_knowledge_attachment_id,
            item.id AS source_item_id,
            item.document_id AS source_document_id,
            item.rag_status AS item_rag_status,
            document.filename AS filename,
            document.file_type AS file_type,
            document.file_size_bytes AS file_size_bytes,
            document.status AS document_status,
            document.created_at_ms AS document_created_at_ms,
            (
                SELECT COUNT(*)
                FROM rag_chunks chunk
                WHERE chunk.document_id = document.id
            ) AS chunk_count
        FROM webui_conversation_knowledge_attachment_items item
        JOIN webui_conversation_knowledge_attachments summary
          ON summary.id = item.knowledge_attachment_id
         AND summary.conv_id = item.conv_id
         AND summary.user_id = item.user_id
        JOIN rag_documents document
          ON document.id = item.document_id
         AND document.conv_id = item.conv_id
         AND document.user_id = item.user_id
        WHERE item.conv_id = ?
          AND item.user_id = ?
          AND item.knowledge_attachment_id = ?
          AND summary.state = 'committed'
          AND summary.source_type != 'linked_knowledge'
          {linked_knowledge_source_operation_sql("summary")}
          AND summary.visible_count > 0
          {knowledge_attachment_summary_ready_for_reference_sql()}
          {linked_knowledge_source_operation_sql("item")}
          AND item.id IN ({item_placeholders})
        ORDER BY item.id ASC
        """


def linked_knowledge_canonical_items_params(
    *,
    source_conv_id: str,
    source_user_id: int,
    source_knowledge_attachment_id: str,
    item_ids: tuple[int, ...],
) -> tuple[str | int, ...]:
    return (
        source_conv_id,
        source_user_id,
        source_knowledge_attachment_id,
        *linked_knowledge_source_operation_params(),
        *knowledge_attachment_ready_for_reference_params(),
        *linked_knowledge_source_operation_params(),
        *item_ids,
    )


def linked_knowledge_active_client_batch_query(*, state_placeholders: str) -> str:
    return f"""
        SELECT *
        FROM webui_conversation_knowledge_attachments
        WHERE conv_id = ?
          AND user_id = ?
          AND client_batch_id = ?
          AND state IN ({state_placeholders})
        LIMIT 1
        """


def linked_knowledge_batch_links_query() -> str:
    return """
        SELECT
            source_conv_id,
            source_user_id,
            source_knowledge_attachment_id,
            source_item_id,
            source_document_id
        FROM rag_linked_documents
        WHERE target_knowledge_attachment_id = ?
        ORDER BY source_item_id ASC
        """


def ensure_linked_knowledge_items_complete(
    items: list[JSONDict],
    *,
    expected_count: int,
) -> None:
    if len(items) != expected_count:
        raise ConflictError("Linked knowledge source item is not available.")
    document_ids: set[str] = set()
    for item in items:
        if item.get("document_status") != "completed" or item.get("item_rag_status") != "completed":
            raise ConflictError("Linked knowledge source item is not completed.")
        document_id = str(item["source_document_id"])
        if document_id in document_ids:
            raise ConflictError("Duplicate linked knowledge document selection.")
        document_ids.add(document_id)


def linked_knowledge_selection_matches_existing(
    *,
    selected_items: list[JSONDict],
    links: list[JSONDict],
) -> bool:
    if len(selected_items) != len(links):
        return False
    for selected_item, link in zip(selected_items, links, strict=True):
        for field_name in LINKED_KNOWLEDGE_SELECTION_FIELDS:
            if selected_item.get(field_name) != link.get(field_name):
                return False
    return True


def linked_knowledge_request_matches_existing(
    *,
    source_conv_id: str,
    source_user_id: int,
    source_knowledge_attachment_id: str,
    item_ids: tuple[int, ...],
    links: list[JSONDict],
) -> bool:
    expected_item_ids = tuple(sorted(item_ids))
    if len(set(expected_item_ids)) != len(expected_item_ids) or len(expected_item_ids) != len(
        links,
    ):
        return False
    for expected_item_id, link in zip(expected_item_ids, links, strict=True):
        if link.get("source_conv_id") != source_conv_id:
            return False
        if link.get("source_user_id") != source_user_id:
            return False
        if link.get("source_knowledge_attachment_id") != source_knowledge_attachment_id:
            return False
        if link.get("source_item_id") != expected_item_id:
            return False
    return True
