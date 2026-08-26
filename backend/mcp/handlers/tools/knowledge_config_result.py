"""SoAI - RAG knowledge config result normalization [backend/mcp/handlers/tools/knowledge_config_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.rag.config_materialization import normalize_stored_rag_config
from core.rag.config_values import RagConfigDefaults
from core.types.json_value import filter_json_mapping
from mcp.auth import parse_config_metadata
from mcp.handlers.tools.knowledge_config_metadata import (
    apply_knowledge_config_metadata_values,
)
from mcp.handlers.tools.rag_config_errors import build_stored_rag_config_mcp_error

if TYPE_CHECKING:
    from core.files.database_types import RAGConversationConfigRecord
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_knowledge_config_result",)


def build_knowledge_config_result(
    *,
    defaults: RagConfigDefaults,
    stored_raw: Mapping[str, JSONValue] | RAGConversationConfigRecord | None,
) -> JSONDict:
    stored = filter_json_mapping(stored_raw)
    normalized = normalize_stored_rag_config(
        defaults,
        stored,
        default_embedding_model=defaults.embedding_model,
        build_error=build_stored_rag_config_mcp_error,
    )
    result = normalized.to_json_dict()
    apply_knowledge_config_metadata_values(result, metadata=parse_config_metadata(stored))
    return result
