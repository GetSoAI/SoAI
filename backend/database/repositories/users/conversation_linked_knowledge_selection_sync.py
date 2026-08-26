"""SoAI - Linked knowledge transaction selection checks [backend/database/repositories/users/conversation_linked_knowledge_selection_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.knowledge_attachment_states import (
    KNOWLEDGE_ACTIVE_ATTACHMENT_STATES,
)
from core.errors.exceptions import ConflictError
from database.core.query_execution import (
    sync_fetch_all_as_dicts,
    sync_fetch_one_as_dict,
)
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
    linked_knowledge_request_matches_existing,
    linked_knowledge_selection_matches_existing,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "fetch_active_linked_knowledge_client_batch",
    "fetch_canonical_linked_knowledge_items",
    "return_matching_linked_knowledge_batch",
    "return_matching_linked_knowledge_request_batch",
)


def fetch_canonical_linked_knowledge_items(
    conn: sqlite3.Connection,
    *,
    source_conv_id: str,
    source_user_id: int,
    source_knowledge_attachment_id: str,
    item_ids: tuple[int, ...],
) -> list[JSONDict]:
    placeholders = linked_knowledge_item_placeholders(item_ids)
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            linked_knowledge_canonical_items_query(item_placeholders=placeholders),
            (
                *linked_knowledge_canonical_items_params(
                    source_conv_id=source_conv_id,
                    source_user_id=source_user_id,
                    source_knowledge_attachment_id=source_knowledge_attachment_id,
                    item_ids=item_ids,
                ),
            ),
        ),
    )
    items = [format_linked_knowledge_item_row(row) for row in rows]
    ensure_linked_knowledge_items_complete(items, expected_count=len(item_ids))
    return items


def fetch_active_linked_knowledge_client_batch(
    conn: sqlite3.Connection,
    *,
    target_conv_id: str,
    target_user_id: int,
    client_batch_id: str,
) -> JSONDict | None:
    states = ",".join("?" for _ in KNOWLEDGE_ACTIVE_ATTACHMENT_STATES)
    row = sync_fetch_one_as_dict(
        conn.execute(
            linked_knowledge_active_client_batch_query(state_placeholders=states),
            (
                target_conv_id,
                target_user_id,
                client_batch_id,
                *KNOWLEDGE_ACTIVE_ATTACHMENT_STATES,
            ),
        ),
    )
    return format_knowledge_attachment_row(row)


def _fetch_link_rows(
    conn: sqlite3.Connection,
    *,
    target_knowledge_attachment_id: str,
) -> list[JSONDict]:
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            linked_knowledge_batch_links_query(),
            (target_knowledge_attachment_id,),
        ),
    )
    return [format_linked_knowledge_link_row(row) for row in rows]


def return_matching_linked_knowledge_batch(
    conn: sqlite3.Connection,
    *,
    selected_items: list[JSONDict],
    existing: JSONDict,
) -> JSONDict:
    if existing.get("source_type") != "linked_knowledge":
        raise ConflictError("Linked knowledge client batch is already bound.")
    links = _fetch_link_rows(
        conn,
        target_knowledge_attachment_id=str(existing["knowledge_attachment_id"]),
    )
    if not linked_knowledge_selection_matches_existing(selected_items=selected_items, links=links):
        raise ConflictError("Linked knowledge client batch selection changed.")
    return existing


def return_matching_linked_knowledge_request_batch(
    conn: sqlite3.Connection,
    *,
    source_conv_id: str,
    source_user_id: int,
    source_knowledge_attachment_id: str,
    item_ids: tuple[int, ...],
    existing: JSONDict,
) -> JSONDict:
    if existing.get("source_type") != "linked_knowledge":
        raise ConflictError("Linked knowledge client batch is already bound.")
    links = _fetch_link_rows(
        conn,
        target_knowledge_attachment_id=str(existing["knowledge_attachment_id"]),
    )
    if not linked_knowledge_request_matches_existing(
        source_conv_id=source_conv_id,
        source_user_id=source_user_id,
        source_knowledge_attachment_id=source_knowledge_attachment_id,
        item_ids=item_ids,
        links=links,
    ):
        raise ConflictError("Linked knowledge client batch selection changed.")
    return existing
