"""SoAI - Shared WebUI RAG config normalization [backend/features/api/routes/webui/conversation_rag/config/normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.files.database_types import RAGConversationConfigRecord
from core.mcp.protocols_rag import MCPRAGProtocol
from core.rag.config_materialization import (
    normalize_stored_rag_config,
    normalize_stored_rag_config_field,
    project_rag_config_record,
)
from core.rag.config_values import (
    normalize_rag_chunking_strategy,
    normalize_rag_embedding_model,
    normalize_rag_enabled,
    normalize_rag_positive_int,
    normalize_rag_retrieval_strategy,
    normalize_rag_similarity_threshold,
    resolve_rag_config_defaults,
)
from features.api.routes.webui.rag_config_models import (
    RAGConversationConfigResponse,
    RAGConversationConfigUpdateFields,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "build_normalized_rag_config_response",
    "build_normalized_rag_config_update_fields",
)


def _build_stored_config_error(field_name: str, exception: ValidationError) -> StateError:
    return StateError(f"Stored RAG config has invalid {field_name} value.", cause=exception)


def _normalize_update_field[Value](
    values: Mapping[str, JSONValue],
    *,
    key: str,
    field_name: str,
    normalizer: Callable[[JSONValue | None], Value],
) -> Value | None:
    if key not in values:
        return None
    value = values.get(key)
    if value is None:
        return None
    return normalize_stored_rag_config_field(
        value,
        field_name=field_name,
        normalizer=normalizer,
    )


def _normalize_update_positive_int(
    values: Mapping[str, JSONValue],
    *,
    key: str,
    default: int,
    minimum: int,
) -> int | None:
    return _normalize_update_field(
        values,
        key=key,
        field_name=key,
        normalizer=lambda value: normalize_rag_positive_int(
            value,
            default=default,
            minimum=minimum,
        ),
    )


def build_normalized_rag_config_update_fields(
    values: Mapping[str, JSONValue] | None,
) -> RAGConversationConfigUpdateFields:
    if values is None:
        return {
            "enabled": None,
            "retrieval_strategy": None,
            "top_k": None,
            "similarity_threshold": None,
            "chunking_strategy": None,
            "chunk_size": None,
            "chunk_overlap": None,
            "embedding_model": None,
        }
    return {
        "enabled": _normalize_update_field(
            values,
            key="enabled",
            field_name="enabled",
            normalizer=normalize_rag_enabled,
        ),
        "retrieval_strategy": _normalize_update_field(
            values,
            key="retrieval_strategy",
            field_name="retrieval_strategy",
            normalizer=normalize_rag_retrieval_strategy,
        ),
        "top_k": _normalize_update_positive_int(
            values,
            key="top_k",
            default=1,
            minimum=1,
        ),
        "similarity_threshold": _normalize_update_field(
            values,
            key="similarity_threshold",
            field_name="similarity_threshold",
            normalizer=lambda value: normalize_rag_similarity_threshold(
                value,
                default=0.0,
            ),
        ),
        "chunking_strategy": _normalize_update_field(
            values,
            key="chunking_strategy",
            field_name="chunking_strategy",
            normalizer=normalize_rag_chunking_strategy,
        ),
        "chunk_size": _normalize_update_positive_int(
            values,
            key="chunk_size",
            default=100,
            minimum=100,
        ),
        "chunk_overlap": _normalize_update_positive_int(
            values,
            key="chunk_overlap",
            default=0,
            minimum=0,
        ),
        "embedding_model": _normalize_update_field(
            values,
            key="embedding_model",
            field_name="embedding_model",
            normalizer=normalize_rag_embedding_model,
        ),
    }


def build_normalized_rag_config_response(
    conv_id: str,
    rag: MCPRAGProtocol,
    config: RAGConversationConfigRecord | None,
) -> RAGConversationConfigResponse:
    defaults = resolve_rag_config_defaults(rag.config)
    stored = None if config is None else project_rag_config_record(config)
    normalized = normalize_stored_rag_config(
        defaults,
        stored,
        default_embedding_model=None,
        build_error=_build_stored_config_error,
    )
    return {
        "conv_id": conv_id,
        "enabled": normalized.enabled,
        "retrieval_strategy": normalized.retrieval.strategy,
        "top_k": normalized.retrieval.top_k,
        "similarity_threshold": normalized.retrieval.similarity_threshold,
        "chunking_strategy": normalized.chunking.strategy,
        "chunk_size": normalized.chunking.chunk_size,
        "chunk_overlap": normalized.chunking.chunk_overlap,
        "embedding_model": normalized.embedding_model,
        "default_embedding_model": None,
    }
