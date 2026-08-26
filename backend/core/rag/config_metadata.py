"""SoAI - Shared RAG config metadata normalization [backend/core/rag/config_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.errors.exceptions import ValidationError
from core.openai.payload_validation import RERANK_API_PROVIDERS
from core.rag.bm25_options import (
    BM25_STOPWORD_MODES,
    BM25_TOKENIZERS,
    DEFAULT_BM25_STOPWORDS_MODE,
    DEFAULT_BM25_TOKENIZER,
)
from core.rag.parameter_validation import validate_finite_float
from core.serialization.json_parsing import parse_json_dict
from core.types.json_value import require_json_dict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue


class NormalizedRAGConfigMetadata(TypedDict):
    rerank_enabled: bool
    rerank_provider: str
    rerank_model: str
    rerank_top_n: int
    hybrid_semantic_weight: float
    hybrid_bm25_weight: float
    hybrid_candidate_multiplier: int
    hybrid_similarity_threshold: float
    hybrid_min_semantic_score: float
    hybrid_min_bm25_score: float
    bm25_tokenizer: str
    bm25_stopwords: str


__all__ = (
    "DEFAULT_HYBRID_SIMILARITY_THRESHOLD",
    "normalize_rag_bm25_settings",
    "normalize_rag_config_metadata",
    "normalize_rag_hybrid_similarity_threshold",
    "normalize_stored_rag_bool",
    "parse_rag_config_metadata_value",
)

DEFAULT_HYBRID_SIMILARITY_THRESHOLD = 0.2

_DEFAULT_RERANK_PROVIDER = "cohere"
_DEFAULT_RERANK_TOP_N = 5
_DEFAULT_HYBRID_SEMANTIC_WEIGHT = 0.7
_DEFAULT_HYBRID_BM25_WEIGHT = 0.3
_DEFAULT_HYBRID_CANDIDATE_MULTIPLIER = 3
_DEFAULT_HYBRID_MIN_SEMANTIC_SCORE = 0.0
_DEFAULT_HYBRID_MIN_BM25_SCORE = 0.0


def normalize_stored_rag_bool(value: JSONValue, *, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise ValidationError(f"Invalid stored RAG {key} (expected bool)")


def parse_rag_config_metadata_value(value: JSONValue | None) -> JSONDict:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            return parse_json_dict(raw, field="stored RAG config_metadata")
        except ValidationError as exception:
            raise ValidationError(
                "Invalid stored RAG config_metadata (expected JSON object)",
            ) from exception
    if value is None:
        return {}
    if isinstance(value, dict):
        return require_json_dict(value, label="stored RAG config_metadata")
    raise ValidationError("Invalid stored RAG config_metadata (expected JSON object)")


def _normalize_metadata_bool(metadata: JSONDict, key: str, default: bool) -> bool:
    raw = metadata.get(key)
    if raw is None:
        return default
    return normalize_stored_rag_bool(raw, key=key)


def _normalize_metadata_positive_int(
    metadata: JSONDict,
    *,
    key: str,
    default: int,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    raw = metadata.get(key)
    if raw is None:
        value = default
    else:
        if isinstance(raw, bool):
            raise ValidationError(f"Invalid stored RAG {key}")
        value = coerce_positive_int(raw, default=default, minimum=minimum)
    if maximum is not None and value > maximum:
        return maximum
    return value


def _normalize_metadata_bounded_float(
    metadata: JSONDict,
    *,
    key: str,
    default: float,
    minimum: float = 0.0,
    maximum: float | None = None,
) -> float:
    raw = metadata.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        raise ValidationError(f"Invalid stored RAG {key}")
    value = validate_finite_float(
        coerce_positive_float(raw, default=default, minimum=minimum),
        field_name=key,
    )
    if maximum is not None:
        return min(maximum, value)
    return value


def normalize_rag_hybrid_similarity_threshold(metadata: JSONDict) -> float:
    return _normalize_metadata_bounded_float(
        metadata,
        key="hybrid_similarity_threshold",
        default=DEFAULT_HYBRID_SIMILARITY_THRESHOLD,
        maximum=1.0,
    )


def _normalize_rerank_provider(metadata: JSONDict) -> str:
    raw = metadata.get("rerank_provider")
    if raw is None:
        return _DEFAULT_RERANK_PROVIDER
    if not isinstance(raw, str):
        raise ValidationError("Invalid stored RAG rerank_provider")
    provider = raw.strip().lower()
    if not provider:
        return _DEFAULT_RERANK_PROVIDER
    if provider not in RERANK_API_PROVIDERS:
        raise ValidationError("Invalid stored RAG rerank_provider")
    return provider


def _normalize_bm25_string_option(
    metadata: JSONDict,
    *,
    key: str,
    default: str,
    valid_values: frozenset[str],
) -> str:
    raw = metadata.get(key)
    if raw is None:
        return default
    if not isinstance(raw, str):
        raise ValidationError(f"Invalid stored RAG {key}")
    normalized = raw.strip().lower()
    if not normalized:
        return default
    if normalized not in valid_values:
        raise ValidationError(f"Invalid stored RAG {key}")
    return normalized


def normalize_rag_bm25_settings(metadata: JSONDict) -> dict[str, str]:
    return {
        "tokenizer": _normalize_bm25_string_option(
            metadata,
            key="bm25_tokenizer",
            default=DEFAULT_BM25_TOKENIZER,
            valid_values=BM25_TOKENIZERS,
        ),
        "stopwords": _normalize_bm25_string_option(
            metadata,
            key="bm25_stopwords",
            default=DEFAULT_BM25_STOPWORDS_MODE,
            valid_values=BM25_STOPWORD_MODES,
        ),
    }


def normalize_rag_config_metadata(metadata: JSONDict) -> NormalizedRAGConfigMetadata:
    provider = _normalize_rerank_provider(metadata)
    bm25_settings = normalize_rag_bm25_settings(metadata)
    rerank_model_raw = metadata.get("rerank_model")
    if rerank_model_raw is not None and not isinstance(rerank_model_raw, str):
        raise ValidationError("Invalid stored RAG rerank_model")
    rerank_model = coerce_optional_trimmed_str(
        rerank_model_raw if isinstance(rerank_model_raw, str) else None,
    )
    return {
        "rerank_enabled": _normalize_metadata_bool(metadata, "rerank_enabled", False),
        "rerank_provider": provider,
        "rerank_model": rerank_model or ("rerank-v3.5" if provider == "cohere" else provider),
        "rerank_top_n": _normalize_metadata_positive_int(
            metadata,
            key="rerank_top_n",
            default=_DEFAULT_RERANK_TOP_N,
        ),
        "hybrid_semantic_weight": _normalize_metadata_bounded_float(
            metadata,
            key="hybrid_semantic_weight",
            default=_DEFAULT_HYBRID_SEMANTIC_WEIGHT,
        ),
        "hybrid_bm25_weight": _normalize_metadata_bounded_float(
            metadata,
            key="hybrid_bm25_weight",
            default=_DEFAULT_HYBRID_BM25_WEIGHT,
        ),
        "hybrid_candidate_multiplier": _normalize_metadata_positive_int(
            metadata,
            key="hybrid_candidate_multiplier",
            default=_DEFAULT_HYBRID_CANDIDATE_MULTIPLIER,
            maximum=10,
        ),
        "hybrid_similarity_threshold": normalize_rag_hybrid_similarity_threshold(metadata),
        "hybrid_min_semantic_score": _normalize_metadata_bounded_float(
            metadata,
            key="hybrid_min_semantic_score",
            default=_DEFAULT_HYBRID_MIN_SEMANTIC_SCORE,
            maximum=1.0,
        ),
        "hybrid_min_bm25_score": _normalize_metadata_bounded_float(
            metadata,
            key="hybrid_min_bm25_score",
            default=_DEFAULT_HYBRID_MIN_BM25_SCORE,
            maximum=1.0,
        ),
        "bm25_tokenizer": bm25_settings["tokenizer"],
        "bm25_stopwords": bm25_settings["stopwords"],
    }
