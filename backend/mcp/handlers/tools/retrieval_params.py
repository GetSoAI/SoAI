"""SoAI - Shared retrieval parameter resolution for RAG tools [backend/mcp/handlers/tools/retrieval_params.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.rag.config_materialization import normalize_stored_rag_config
from core.rag.config_metadata import normalize_rag_hybrid_similarity_threshold
from core.rag.config_values import resolve_rag_config_defaults
from core.rag.tool_parameters import (
    ResolvedRagRetrievalParams,
    resolve_rag_retrieval_params,
)
from core.types.json_value import filter_json_mapping
from mcp.auth import parse_config_metadata
from mcp.handlers.tools.internal_protocols import RetrievalParamsSourceProtocol
from mcp.handlers.tools.rag_config_errors import build_stored_rag_config_mcp_error
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("resolve_retrieval_params",)


async def resolve_retrieval_params(
    *,
    rag: RetrievalParamsSourceProtocol,
    conv_id: str,
    arguments: JSONDict,
    top_k_max: int | None = None,
) -> ResolvedRagRetrievalParams:
    defaults = resolve_rag_config_defaults(rag.config)
    stored_raw = await rag.database_files.get_rag_config(conv_id)
    stored = filter_json_mapping(stored_raw)
    normalized_config = normalize_stored_rag_config(
        defaults,
        stored,
        default_embedding_model=defaults.embedding_model,
        build_error=build_stored_rag_config_mcp_error,
    )
    parsed_metadata = parse_config_metadata(stored)
    try:
        metadata: JSONDict = {
            "hybrid_similarity_threshold": normalize_rag_hybrid_similarity_threshold(
                parsed_metadata,
            ),
        }
    except ValidationError as exception:
        raise MCPJSONRPCError(
            -32603,
            "Invalid stored RAG hybrid_similarity_threshold",
        ) from exception
    try:
        return resolve_rag_retrieval_params(
            defaults=defaults,
            config=normalized_config,
            metadata=metadata,
            arguments=arguments,
            top_k_max=top_k_max,
        )
    except ValidationError as exception:
        raise MCPJSONRPCError(-32602, str(exception)) from exception
