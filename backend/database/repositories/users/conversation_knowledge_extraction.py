"""SoAI - Knowledge attachment extraction outcome projection [backend/database/repositories/users/conversation_knowledge_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.files.extraction_summary import read_missing_capabilities
from core.serialization.json_parsing import parse_json_dict, parse_json_str_list

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRow

__all__ = ("KNOWLEDGE_SUMMARY_COLUMNS", "knowledge_summary_missing_capabilities")

KNOWLEDGE_SUMMARY_COLUMNS = """*, (
    SELECT json_group_array(source.metadata) FROM (
        SELECT document.metadata
        FROM webui_conversation_knowledge_attachment_items item
        JOIN rag_documents document ON document.id = item.document_id
          AND document.conv_id = item.conv_id AND document.user_id = item.user_id
        WHERE item.knowledge_attachment_id = webui_conversation_knowledge_attachments.id
          AND item.conv_id = webui_conversation_knowledge_attachments.conv_id
          AND item.user_id = webui_conversation_knowledge_attachments.user_id
          AND document.metadata IS NOT NULL
        UNION ALL
        SELECT document.metadata
        FROM rag_linked_documents link
        JOIN rag_documents document ON document.id = link.source_document_id
          AND document.conv_id = link.source_conv_id
          AND document.user_id = link.source_user_id
        WHERE link.status = 'active'
          AND link.target_knowledge_attachment_id = webui_conversation_knowledge_attachments.id
          AND link.target_conv_id = webui_conversation_knowledge_attachments.conv_id
          AND link.target_user_id = webui_conversation_knowledge_attachments.user_id
          AND link.source_user_id = webui_conversation_knowledge_attachments.user_id
          AND document.metadata IS NOT NULL
    ) source
) AS extraction_metadata"""


def knowledge_summary_missing_capabilities(row: SQLiteRow) -> tuple[str, ...]:
    raw = row.get("extraction_metadata")
    if raw is None:
        return ()
    if not isinstance(raw, str | bytes):
        raise StateError("Knowledge attachment extraction metadata is invalid.")
    capabilities: set[str] = set()
    for metadata in parse_json_str_list(raw, field="extraction_metadata"):
        capabilities.update(
            read_missing_capabilities(
                parse_json_dict(metadata, field="document extraction metadata")
            )
        )
    return tuple(sorted(capabilities))
