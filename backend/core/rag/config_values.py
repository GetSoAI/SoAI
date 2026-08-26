"""SoAI - Shared RAG configuration value normalization [backend/core/rag/config_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_float, coerce_positive_int
from core.errors.exceptions import StateError, ValidationError
from core.rag.parameter_validation import (
    normalize_chunking_strategy,
    normalize_retrieval_strategy,
    validate_finite_float,
)
from core.types.json import JSONValue
from core.validation.booleans import parse_bool_flag_or_none
from core.validation.strings import coerce_optional_trimmed_str, require_trimmed_json_text

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "DEFAULT_CHUNKING_STRATEGY",
    "DEFAULT_RETRIEVAL_STRATEGY",
    "RAG_CONFIG_VALUE_FIELDS",
    "RagConfigDefaults",
    "normalize_rag_chunking_strategy",
    "normalize_rag_embedding_model",
    "normalize_rag_enabled",
    "normalize_rag_positive_int",
    "normalize_rag_retrieval_strategy",
    "normalize_rag_similarity_threshold",
    "resolve_rag_config_defaults",
)

DEFAULT_RETRIEVAL_STRATEGY = "similarity"
DEFAULT_CHUNKING_STRATEGY = "token_based"
RAG_CONFIG_VALUE_FIELDS = frozenset(
    {
        "enabled",
        "retrieval_strategy",
        "top_k",
        "similarity_threshold",
        "chunking_strategy",
        "chunk_size",
        "chunk_overlap",
        "embedding_model",
    }
)


@dataclass(frozen=True, slots=True)
class RagConfigDefaults:
    top_k: int
    similarity_threshold: float
    chunk_size: int
    chunk_overlap: int
    embedding_model: str


def _resolve_default_positive_int(
    config: ConfigProtocol,
    *,
    key: str,
    default: int,
    minimum: int,
) -> int:
    try:
        value = config.get(key, default)
        if isinstance(value, bool):
            raise ValidationError(f"{key} must be an integer.")
        return coerce_positive_int(value, default=default, minimum=minimum)
    except ValidationError as exception:
        raise StateError(f"Invalid configuration: {key}") from exception


def _resolve_default_similarity_threshold(config: ConfigProtocol) -> float:
    try:
        return min(
            1.0,
            validate_finite_float(
                coerce_positive_float(
                    config.get("TOOLS.RAG.DEFAULT_SIMILARITY_THRESHOLD", 0.3),
                    default=0.3,
                    minimum=0.0,
                ),
                field_name="TOOLS.RAG.DEFAULT_SIMILARITY_THRESHOLD",
            ),
        )
    except ValidationError as exception:
        raise StateError(
            "Invalid configuration: TOOLS.RAG.DEFAULT_SIMILARITY_THRESHOLD",
        ) from exception


def resolve_rag_config_defaults(config: ConfigProtocol) -> RagConfigDefaults:
    embedding_model_raw = config.get("TOOLS.RAG.DEFAULT_EMBEDDING_MODEL", "auto")
    if not isinstance(embedding_model_raw, str):
        raise StateError(
            "Invalid configuration: TOOLS.RAG.DEFAULT_EMBEDDING_MODEL must be a non-empty string.",
        )
    embedding_model = coerce_optional_trimmed_str(embedding_model_raw)
    if embedding_model is None:
        raise StateError(
            "Invalid configuration: TOOLS.RAG.DEFAULT_EMBEDDING_MODEL must be a non-empty string.",
        )
    return RagConfigDefaults(
        top_k=_resolve_default_positive_int(
            config,
            key="TOOLS.RAG.DEFAULT_TOP_K",
            default=5,
            minimum=1,
        ),
        similarity_threshold=_resolve_default_similarity_threshold(config),
        chunk_size=_resolve_default_positive_int(
            config,
            key="TOOLS.RAG.DEFAULT_CHUNK_SIZE",
            default=500,
            minimum=100,
        ),
        chunk_overlap=_resolve_default_positive_int(
            config,
            key="TOOLS.RAG.DEFAULT_CHUNK_OVERLAP",
            default=100,
            minimum=0,
        ),
        embedding_model=embedding_model,
    )


def normalize_rag_enabled(value: JSONValue | None) -> bool:
    if value is None:
        parsed = None
    elif isinstance(value, str | int | float | bool):
        parsed = parse_bool_flag_or_none(value)
    else:
        parsed = None
    if parsed is None:
        raise ValidationError("enabled must be a boolean value.")
    return parsed


def normalize_rag_positive_int(
    value: JSONValue | None,
    *,
    default: int,
    minimum: int,
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise ValidationError("value must be an integer.")
    return coerce_positive_int(value, default=default, minimum=minimum)


def normalize_rag_similarity_threshold(value: JSONValue | None, *, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise ValidationError("similarity_threshold must be a number.")
    return min(
        1.0,
        validate_finite_float(
            coerce_positive_float(value, default=default, minimum=0.0),
            field_name="stored RAG similarity_threshold",
        ),
    )


def normalize_rag_retrieval_strategy(value: JSONValue | None) -> str:
    if value is None:
        return DEFAULT_RETRIEVAL_STRATEGY
    normalized = require_trimmed_json_text(
        value,
        error_message="retrieval_strategy must be a non-empty string.",
    )
    return normalize_retrieval_strategy(normalized)


def normalize_rag_chunking_strategy(value: JSONValue | None) -> str:
    if value is None:
        return DEFAULT_CHUNKING_STRATEGY
    normalized = require_trimmed_json_text(
        value,
        error_message="chunking_strategy must be a non-empty string.",
    )
    return normalize_chunking_strategy(normalized)


def normalize_rag_embedding_model(value: JSONValue | None) -> str | None:
    if value is None:
        return None
    return require_trimmed_json_text(
        value,
        error_message="embedding_model must be a non-empty string.",
    )
