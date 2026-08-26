"""SoAI - MCP Knowledge tool guidance helpers [backend/mcp/handlers/tools/knowledge_guidance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.rag.knowledge_prompt_contract import KNOWLEDGE_PROMPT_UPLOAD_GUIDANCE
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "build_empty_knowledge_list_result",
    "require_knowledge_documents_for_operation",
    "require_knowledge_search_sources_for_operation",
)


async def require_knowledge_documents_for_operation(
    *,
    rag: MCPRAGInternalProtocol,
    conv_id: str,
    require_searchable: bool = True,
) -> JSONDict:
    raw_counts = await rag.database_files.get_rag_counts_for_conversation(conv_id)
    counts = coerce_json_dict(raw_counts)
    if counts is None:
        raise MCPJSONRPCError(-32603, "Knowledge document counts are unavailable.")
    document_count = _count(counts, "document_count")
    if document_count <= 0:
        raise MCPJSONRPCError(-32603, KNOWLEDGE_PROMPT_UPLOAD_GUIDANCE)
    if require_searchable and (
        _count(counts, "completed") <= 0 or _count(counts, "chunk_count") <= 0
    ):
        raise MCPJSONRPCError(-32603, _build_processing_status_message(counts))
    return counts


async def require_knowledge_search_sources_for_operation(
    *,
    rag: MCPRAGInternalProtocol,
    conv_id: str,
    user_id: int,
) -> JSONDict:
    raw_counts = await rag.database_files.get_rag_counts_for_conversation(conv_id)
    counts = coerce_json_dict(raw_counts)
    if counts is None:
        raise MCPJSONRPCError(-32603, "Knowledge document counts are unavailable.")
    if _count(counts, "completed") > 0 and _count(counts, "chunk_count") > 0:
        return counts
    linked_documents = await rag.database_files.get_active_linked_rag_documents(conv_id, user_id)
    if linked_documents:
        return counts
    if _count(counts, "document_count") <= 0:
        raise MCPJSONRPCError(-32603, KNOWLEDGE_PROMPT_UPLOAD_GUIDANCE)
    raise MCPJSONRPCError(-32603, _build_processing_status_message(counts))


def build_empty_knowledge_list_result() -> JSONDict:
    return {
        "documents": [],
        "count": 0,
        "guidance": KNOWLEDGE_PROMPT_UPLOAD_GUIDANCE,
    }


def _build_processing_status_message(counts: JSONDict) -> str:
    return (
        "Knowledge documents exist but are not searchable yet. "
        f"queued={_count(counts, 'queued')}, "
        f"processing={_processing_count(counts)}, "
        f"completed={_count(counts, 'completed')}, "
        f"error={_count(counts, 'error')}, "
        f"searchable_chunks={_count(counts, 'chunk_count')}."
    )


def _processing_count(counts: JSONDict) -> int:
    return sum(_count(counts, key) for key in ("fetching", "parsing", "chunking", "embedding"))


def _count(counts: JSONDict, key: str) -> int:
    value = counts.get(key)
    return int(value) if is_strict_int(value) else 0
