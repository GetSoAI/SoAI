"""SoAI - Linked knowledge reusable catalog queries [backend/database/repositories/users/conversation_linked_knowledge_catalog_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.core.query_execution import query_to_dicts
from database.repositories.users.conversation_attachment_knowledge_readiness import (
    knowledge_attachment_ready_for_reference_params,
    knowledge_attachment_ready_for_reference_sql,
)
from database.repositories.users.conversation_attachment_rows import (
    format_knowledge_attachment_row,
)
from database.repositories.users.conversation_linked_knowledge_selection_core import (
    linked_knowledge_catalog_source_exists_sql,
    linked_knowledge_source_operation_params,
    linked_knowledge_source_operation_sql,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("list_reusable_knowledge_attachments_query",)

_REUSABLE_KNOWLEDGE_MAX_LIMIT = 50


def _reusable_knowledge_base_sql() -> str:
    return f"""
    SELECT *
    FROM webui_conversation_knowledge_attachments
    WHERE user_id = ?
      AND state = 'committed'
      AND source_type != 'linked_knowledge'
      {linked_knowledge_source_operation_sql("webui_conversation_knowledge_attachments")}
      {knowledge_attachment_ready_for_reference_sql()}
      {linked_knowledge_catalog_source_exists_sql()}
"""


async def list_reusable_knowledge_attachments_query(
    database: aiosqlite.Connection,
    user_id: int,
    query: str | None,
    limit: int,
) -> list[JSONDict]:
    normalized_query = query.strip() if isinstance(query, str) and query.strip() else None
    bounded_limit = min(max(int(limit), 1), _REUSABLE_KNOWLEDGE_MAX_LIMIT)
    reusable_knowledge_base_sql = _reusable_knowledge_base_sql()
    source_operation_params = linked_knowledge_source_operation_params()
    readiness_params = knowledge_attachment_ready_for_reference_params()
    if normalized_query is None:
        rows = await query_to_dicts(
            database,
            f"{reusable_knowledge_base_sql}\nORDER BY updated_at_ms DESC, id DESC\nLIMIT ?",
            (
                user_id,
                *source_operation_params,
                *readiness_params,
                *source_operation_params,
                bounded_limit,
            ),
        )
    else:
        rows = await query_to_dicts(
            database,
            f"{reusable_knowledge_base_sql}\n  AND instr(lower(title), lower(?)) > 0\nORDER BY updated_at_ms DESC, id DESC\nLIMIT ?",
            (
                user_id,
                *source_operation_params,
                *readiness_params,
                *source_operation_params,
                normalized_query,
                bounded_limit,
            ),
        )
    items: list[JSONDict] = []
    for row in rows:
        summary = format_knowledge_attachment_row(row)
        if summary is not None:
            items.append(summary)
    return items
