"""SoAI - MCP RAG search embedding helpers [backend/mcp/rag/search_ops_embedding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.mcp.schema import is_auto_embedding_model_selector
from core.serialization.json_parsing import parse_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from mcp.rag.embedding_model import persist_effective_embedding_model
from mcp.storage.embeddings import generate_embeddings

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "generate_query_embedding_and_persist_effective_model_if_needed",
    "load_collection_constraints",
    "validate_embedding_dimensions_or_raise",
)


def _parse_collection_metadata_value(metadata_value: JSONValue | None) -> JSONDict:
    if metadata_value is None:
        return {}
    if isinstance(metadata_value, dict):
        return metadata_value
    if isinstance(metadata_value, str):
        raw = metadata_value.strip()
        if not raw:
            return {}
        try:
            return parse_json_dict(raw, field="RAG collection metadata")
        except ValidationError as exception:
            raise ValidationError("RAG collection metadata must be a JSON object.") from exception
    raise ValidationError("RAG collection metadata must be JSON.")


async def load_collection_constraints(
    self: MCPRAGInternalProtocol,
    conv_id: str,
) -> tuple[int | None, str | None]:
    collection_meta = await self.database_files.get_rag_collection_metadata(conv_id)
    expected_dims: int | None = None
    collection_effective_model: str | None = None
    if not isinstance(collection_meta, dict):
        return expected_dims, collection_effective_model
    raw_dims = collection_meta.get("embedding_dimensions")
    if isinstance(raw_dims, int | float | str) and not isinstance(raw_dims, bool):
        try:
            expected_dims = int(raw_dims)
        except (TypeError, ValueError):
            expected_dims = None
    metadata_value = collection_meta.get("metadata")
    metadata = _parse_collection_metadata_value(metadata_value)
    effective_model_value = metadata.get("effective_model")
    normalized_effective_model = coerce_optional_trimmed_str(
        effective_model_value if isinstance(effective_model_value, str) else None,
    )
    if normalized_effective_model is not None:
        collection_effective_model = normalized_effective_model
    return expected_dims, collection_effective_model


async def generate_query_embedding_and_persist_effective_model_if_needed(
    *,
    self: MCPRAGInternalProtocol,
    query: str,
    conv_id: str,
    user_id: int,
    resolved_embedding_model: str | None,
    expected_embedding_selector: str | None,
) -> tuple[list[float] | None, str | None]:
    out_actual_model: list[str] = []
    query_embedding = await generate_embeddings(
        self.storage,
        [query],
        conv_id,
        user_id=user_id,
        embedding_model=resolved_embedding_model,
        out_actual_model=out_actual_model,
    )
    query_vector = query_embedding[0] if query_embedding and query_embedding[0] else None
    actual_model_value = coerce_optional_trimmed_str(
        out_actual_model[0] if out_actual_model and isinstance(out_actual_model[0], str) else None,
    )
    if (
        isinstance(resolved_embedding_model, str)
        and is_auto_embedding_model_selector(resolved_embedding_model)
        and actual_model_value
    ):
        await persist_effective_embedding_model(
            self,
            conv_id=conv_id,
            user_id=user_id,
            embedding_model=actual_model_value,
            expected_embedding_selector=expected_embedding_selector,
        )
    return query_vector, actual_model_value


def validate_embedding_dimensions_or_raise(
    *,
    expected_dims: int | None,
    query_vector: list[float],
    request_model: str | None,
    actual_model: str | None,
    collection_effective_model: str | None,
) -> None:
    if expected_dims is None or expected_dims <= 0:
        return
    if len(query_vector) == expected_dims:
        return
    effective_desc = collection_effective_model or "unknown"
    query_model_used = actual_model or request_model or "auto"
    raise ValidationError(
        f"Embedding dimension mismatch: expected {expected_dims}, got {len(query_vector)}. Query effective model: {query_model_used}. Collection effective model: {effective_desc}. Run knowledge_reindex to rebuild the collection with the correct embedding model.",
    )
