"""SoAI - Conversation-local RAG configuration helpers [backend/core/rag/conversation_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.requests import UpdateRAGConfigRequest
from core.errors.exceptions import StateError, ValidationError
from core.rag.config_metadata import normalize_stored_rag_bool

if TYPE_CHECKING:
    from core.files.database_types import RAGConversationConfigRecord
    from core.files.protocols_database import DatabaseFilesProtocol

__all__ = (
    "ensure_conversation_rag_enabled",
    "read_rag_enabled_from_config",
)


def read_rag_enabled_from_config(raw_config: RAGConversationConfigRecord | None) -> bool:
    if raw_config is None:
        return True
    try:
        enabled_value = raw_config["enabled"]
    except KeyError as exception:
        raise StateError("Stored RAG config has missing enabled value.") from exception
    try:
        return normalize_stored_rag_bool(enabled_value, key="enabled")
    except ValidationError as exception:
        raise StateError("Stored RAG config has invalid enabled value.") from exception


async def ensure_conversation_rag_enabled(
    database_files: DatabaseFilesProtocol,
    conv_id: str,
) -> bool:
    raw_config = await database_files.get_rag_config(conv_id)
    if raw_config is None:
        return False
    if read_rag_enabled_from_config(raw_config):
        return False
    await database_files.update_rag_config(UpdateRAGConfigRequest(conv_id=conv_id, enabled=True))
    return True
