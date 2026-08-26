"""SoAI - Linked knowledge read queries [backend/database/repositories/users/conversation_linked_knowledge_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.attachments.knowledge_attachment_states import (
    KNOWLEDGE_ACTIVE_ATTACHMENT_STATES,
)
from core.errors.exceptions import ConflictError
from database.core.query_execution import query_to_dicts
from database.repositories.users.conversation_attachment_rows import (
    format_knowledge_attachment_row,
)
from database.repositories.users.conversation_linked_knowledge_rows import (
    format_linked_knowledge_item_row,
    format_linked_knowledge_link_row,
)
from database.repositories.users.conversation_linked_knowledge_selection_core import (
    ensure_linked_knowledge_items_complete,
    linked_knowledge_active_client_batch_query,
    linked_knowledge_batch_links_query,
    linked_knowledge_canonical_items_params,
    linked_knowledge_canonical_items_query,
    linked_knowledge_item_placeholders,
    linked_knowledge_selection_matches_existing,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_linked_knowledge_item_preview_query",
    "prepare_linked_knowledge_use_query",
)

_PREVIEW_CHUNK_LIMIT = 3
_PREVIEW_TEXT_MAX_CHARS = 6000


async def _fetch_canonical_items(
    database: aiosqlite.Connection,
    *,
    source_conv_id: str,
    source_user_id: int,
    source_knowledge_attachment_id: str,
    item_ids: tuple[int, ...],
) -> list[JSONDict]:
    placeholders = linked_knowledge_item_placeholders(item_ids)
    rows = await query_to_dicts(
        database,
        linked_knowledge_canonical_items_query(item_placeholders=placeholders),
        (
            *linked_knowledge_canonical_items_params(
                source_conv_id=source_conv_id,
                source_user_id=source_user_id,
                source_knowledge_attachment_id=source_knowledge_attachment_id,
                item_ids=item_ids,
            ),
        ),
    )
    items = [format_linked_knowledge_item_row(row) for row in rows]
    ensure_linked_knowledge_items_complete(items, expected_count=len(item_ids))
    return items


async def _fetch_active_client_batch(
    database: aiosqlite.Connection,
    *,
    target_conv_id: str,
    target_user_id: int,
    client_batch_id: str,
) -> JSONDict | None:
    states = ",".join("?" for _ in KNOWLEDGE_ACTIVE_ATTACHMENT_STATES)
    rows = await query_to_dicts(
        database,
        linked_knowledge_active_client_batch_query(state_placeholders=states),
        (
            target_conv_id,
            target_user_id,
            client_batch_id,
            *KNOWLEDGE_ACTIVE_ATTACHMENT_STATES,
        ),
    )
    if not rows:
        return None
    return format_knowledge_attachment_row(rows[0])


async def _fetch_existing_link_rows(
    database: aiosqlite.Connection,
    *,
    target_knowledge_attachment_id: str,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        linked_knowledge_batch_links_query(),
        (target_knowledge_attachment_id,),
    )
    return [format_linked_knowledge_link_row(row) for row in rows]


def _selected_item_document_id(item: JSONDict) -> str:
    document_id = item.get("source_document_id")
    if not isinstance(document_id, str) or not document_id.strip():
        raise ConflictError("Linked knowledge source document is invalid.")
    return document_id


async def prepare_linked_knowledge_use_query(
    database: aiosqlite.Connection,
    target_conv_id: str,
    target_user_id: int,
    source_conv_id: str,
    source_user_id: int,
    source_knowledge_attachment_id: str,
    item_ids: tuple[int, ...],
    client_batch_id: str,
) -> JSONDict:
    selected_items = await _fetch_canonical_items(
        database,
        source_conv_id=source_conv_id,
        source_user_id=source_user_id,
        source_knowledge_attachment_id=source_knowledge_attachment_id,
        item_ids=item_ids,
    )
    existing = await _fetch_active_client_batch(
        database,
        target_conv_id=target_conv_id,
        target_user_id=target_user_id,
        client_batch_id=client_batch_id,
    )
    if existing is None:
        return {"selected_items": selected_items, "existing_summary": None}
    if existing.get("source_type") != "linked_knowledge":
        raise ConflictError("Linked knowledge client batch is already bound.")
    links = await _fetch_existing_link_rows(
        database,
        target_knowledge_attachment_id=str(existing["knowledge_attachment_id"]),
    )
    if not linked_knowledge_selection_matches_existing(selected_items=selected_items, links=links):
        raise ConflictError("Linked knowledge client batch selection changed.")
    return {"selected_items": selected_items, "existing_summary": existing}


async def get_linked_knowledge_item_preview_query(
    database: aiosqlite.Connection,
    source_conv_id: str,
    source_user_id: int,
    source_knowledge_attachment_id: str,
    item_id: int,
    document_id: str | None,
) -> JSONDict:
    items = await _fetch_canonical_items(
        database,
        source_conv_id=source_conv_id,
        source_user_id=source_user_id,
        source_knowledge_attachment_id=source_knowledge_attachment_id,
        item_ids=(item_id,),
    )
    item = items[0]
    if document_id is not None and item.get("source_document_id") != document_id:
        raise ConflictError("Linked knowledge document id does not match the selected item.")
    chunks = await query_to_dicts(
        database,
        """
        SELECT content
        FROM rag_chunks
        WHERE document_id = ?
        ORDER BY chunk_index ASC
        LIMIT ?
        """,
        (_selected_item_document_id(item), _PREVIEW_CHUNK_LIMIT),
    )
    text_parts: list[str] = []
    total_length = 0
    for chunk in chunks:
        content = chunk.get("content")
        if isinstance(content, str) and content:
            remaining = _PREVIEW_TEXT_MAX_CHARS - total_length
            if remaining <= 0:
                break
            text_parts.append(content[:remaining])
            total_length += len(text_parts[-1])
    return {
        "state": "available",
        "preview_type": "text" if text_parts else "metadata",
        "document": item,
        "text": "\n\n".join(text_parts) if text_parts else None,
    }
