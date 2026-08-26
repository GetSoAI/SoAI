"""SoAI - RAG tool parameter resolution [backend/core/rag/tool_parameters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.errors.exceptions import ValidationError
from core.rag.config_materialization import NormalizedRagConfig
from core.rag.config_metadata import normalize_rag_hybrid_similarity_threshold
from core.rag.config_values import RagConfigDefaults
from core.rag.parameter_validation import (
    coerce_chunking_strategy,
    normalize_retrieval_strategy,
    validate_finite_float,
)
from core.types.json import JSONDict, JSONValue

__all__ = (
    "ResolvedRagRetrievalParams",
    "resolve_rag_ingest_params",
    "resolve_rag_retrieval_params",
)


@dataclass(frozen=True, slots=True)
class ResolvedRagRetrievalParams:
    retrieval_strategy: str
    top_k: int
    similarity_threshold: float


def _resolve_requested_retrieval_strategy(
    arguments: JSONDict,
    configured_strategy: str,
) -> str:
    requested_strategy = arguments.get("retrieval_strategy")
    if requested_strategy is None:
        return configured_strategy
    if not isinstance(requested_strategy, str) or not requested_strategy.strip():
        raise ValidationError("retrieval_strategy must be a non-empty string")
    return normalize_retrieval_strategy(requested_strategy)


def _resolve_requested_top_k(
    arguments: JSONDict,
    *,
    defaults: RagConfigDefaults,
    configured_top_k: int,
    top_k_max: int | None,
) -> int:
    top_k_input = arguments.get("top_k")
    if top_k_input is None:
        resolved_top_k = configured_top_k
    else:
        if isinstance(top_k_input, bool):
            raise ValidationError("top_k must be an integer >= 1")
        resolved_top_k = coerce_positive_int(
            top_k_input,
            default=defaults.top_k,
            minimum=1,
        )
    if top_k_max is not None and resolved_top_k > top_k_max:
        raise ValidationError(f"top_k must be <= {top_k_max}")
    return resolved_top_k


def _resolve_hybrid_similarity_threshold(metadata: JSONDict) -> float:
    return normalize_rag_hybrid_similarity_threshold(metadata)


def _resolve_requested_similarity_threshold(
    arguments: JSONDict,
    *,
    defaults: RagConfigDefaults,
    configured_threshold: float,
    metadata: JSONDict,
    retrieval_strategy: str,
) -> float:
    threshold_input = arguments.get("similarity_threshold")
    if threshold_input is None:
        if retrieval_strategy == "hybrid":
            return _resolve_hybrid_similarity_threshold(metadata)
        return configured_threshold
    if isinstance(threshold_input, bool):
        raise ValidationError("similarity_threshold must be a number in [0.0, 1.0]")
    return min(
        1.0,
        validate_finite_float(
            coerce_positive_float(
                threshold_input,
                default=defaults.similarity_threshold,
                minimum=0.0,
            ),
            field_name="similarity_threshold",
        ),
    )


def resolve_rag_retrieval_params(
    *,
    defaults: RagConfigDefaults,
    config: NormalizedRagConfig,
    metadata: JSONDict,
    arguments: JSONDict,
    top_k_max: int | None = None,
) -> ResolvedRagRetrievalParams:
    retrieval_strategy = _resolve_requested_retrieval_strategy(
        arguments,
        config.retrieval.strategy,
    )
    return ResolvedRagRetrievalParams(
        retrieval_strategy=retrieval_strategy,
        top_k=_resolve_requested_top_k(
            arguments,
            defaults=defaults,
            configured_top_k=config.retrieval.top_k,
            top_k_max=top_k_max,
        ),
        similarity_threshold=_resolve_requested_similarity_threshold(
            arguments,
            defaults=defaults,
            configured_threshold=config.retrieval.similarity_threshold,
            metadata=metadata,
            retrieval_strategy=retrieval_strategy,
        ),
    )


def _resolve_ingest_int_argument(
    arguments: JSONDict,
    key: str,
    *,
    default: int,
    minimum: int,
) -> int:
    value = arguments.get(key, default)
    if isinstance(value, bool):
        raise ValidationError(f"{key} must be an integer >= {minimum}")
    return coerce_positive_int(value, default=default, minimum=minimum)


def resolve_rag_ingest_params(
    *,
    defaults: RagConfigDefaults,
    arguments: JSONDict,
) -> dict[str, JSONValue]:
    chunking_strategy_raw = arguments.get("chunking_strategy")
    chunking_strategy_value = (
        chunking_strategy_raw if isinstance(chunking_strategy_raw, str) else None
    )
    return {
        "chunk_size": _resolve_ingest_int_argument(
            arguments,
            "chunk_size",
            default=defaults.chunk_size,
            minimum=100,
        ),
        "chunk_overlap": _resolve_ingest_int_argument(
            arguments,
            "chunk_overlap",
            default=defaults.chunk_overlap,
            minimum=0,
        ),
        "embedding_model": arguments.get("embedding_model"),
        "chunking_strategy": coerce_chunking_strategy(chunking_strategy_value),
    }
