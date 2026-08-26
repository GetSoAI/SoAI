"""SoAI - RAG config materialization [backend/core/rag/config_materialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

from core.errors.exceptions import StateError, ValidationError
from core.rag.config_metadata import normalize_stored_rag_bool
from core.rag.config_values import (
    RagConfigDefaults,
    normalize_rag_chunking_strategy,
    normalize_rag_embedding_model,
    normalize_rag_positive_int,
    normalize_rag_retrieval_strategy,
    normalize_rag_similarity_threshold,
)
from core.rag.parameter_validation import validate_chunking_window
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from core.files.database_types import RAGConversationConfigRecord

__all__ = (
    "NormalizedRagChunking",
    "NormalizedRagConfig",
    "NormalizedRagRetrieval",
    "normalize_stored_rag_config",
    "normalize_stored_rag_config_field",
    "project_rag_config_record",
)


@dataclass(frozen=True, slots=True)
class NormalizedRagRetrieval:
    strategy: str
    top_k: int
    similarity_threshold: float


@dataclass(frozen=True, slots=True)
class NormalizedRagChunking:
    strategy: str
    chunk_size: int
    chunk_overlap: int


@dataclass(frozen=True, slots=True)
class NormalizedRagConfig:
    enabled: bool
    retrieval: NormalizedRagRetrieval
    chunking: NormalizedRagChunking
    embedding_model: str | None

    def to_json_dict(self) -> JSONDict:
        return {
            "enabled": self.enabled,
            "retrieval_strategy": self.retrieval.strategy,
            "top_k": self.retrieval.top_k,
            "similarity_threshold": self.retrieval.similarity_threshold,
            "chunking_strategy": self.chunking.strategy,
            "chunk_size": self.chunking.chunk_size,
            "chunk_overlap": self.chunking.chunk_overlap,
            "embedding_model": self.embedding_model,
        }


def project_rag_config_record(config: RAGConversationConfigRecord) -> JSONDict:
    return {
        "enabled": config["enabled"],
        "retrieval_strategy": config["retrieval_strategy"],
        "top_k": config["top_k"],
        "similarity_threshold": config["similarity_threshold"],
        "chunking_strategy": config["chunking_strategy"],
        "chunk_size": config["chunk_size"],
        "chunk_overlap": config["chunk_overlap"],
        "embedding_model": config["embedding_model"],
    }


def _raise_stored_rag_config_error(
    field_name: str,
    exception: ValidationError,
    build_error: Callable[[str, ValidationError], Exception] | None,
) -> NoReturn:
    if build_error is None:
        raise ValidationError(f"Invalid stored RAG {field_name}") from exception
    raise build_error(field_name, exception) from exception


def normalize_stored_rag_config_field[Value](
    value: JSONValue | None,
    *,
    field_name: str,
    normalizer: Callable[[JSONValue | None], Value],
) -> Value:
    try:
        return normalizer(value)
    except ValidationError as exception:
        raise StateError(
            f"Stored RAG config has invalid {field_name} value.",
            cause=exception,
        ) from exception


def normalize_stored_rag_config(
    defaults: RagConfigDefaults,
    stored: Mapping[str, JSONValue] | None,
    *,
    default_embedding_model: str | None,
    build_error: Callable[[str, ValidationError], Exception] | None = None,
) -> NormalizedRagConfig:
    stored_values = stored or {}
    enabled_raw = stored_values.get("enabled")
    enabled = True
    if enabled_raw is not None:
        try:
            enabled = normalize_stored_rag_bool(enabled_raw, key="enabled")
        except ValidationError as exception:
            _raise_stored_rag_config_error("enabled", exception, build_error)
    try:
        retrieval_strategy = normalize_rag_retrieval_strategy(
            stored_values.get("retrieval_strategy"),
        )
    except ValidationError as exception:
        _raise_stored_rag_config_error("retrieval_strategy", exception, build_error)
    try:
        top_k = normalize_rag_positive_int(
            stored_values.get("top_k"),
            default=defaults.top_k,
            minimum=1,
        )
    except ValidationError as exception:
        _raise_stored_rag_config_error("top_k", exception, build_error)
    try:
        similarity_threshold = normalize_rag_similarity_threshold(
            stored_values.get("similarity_threshold"),
            default=defaults.similarity_threshold,
        )
    except ValidationError as exception:
        _raise_stored_rag_config_error("similarity_threshold", exception, build_error)
    try:
        chunking_strategy = normalize_rag_chunking_strategy(stored_values.get("chunking_strategy"))
    except ValidationError as exception:
        _raise_stored_rag_config_error("chunking_strategy", exception, build_error)
    try:
        chunk_size = normalize_rag_positive_int(
            stored_values.get("chunk_size"),
            default=defaults.chunk_size,
            minimum=100,
        )
    except ValidationError as exception:
        _raise_stored_rag_config_error("chunk_size", exception, build_error)
    try:
        chunk_overlap = normalize_rag_positive_int(
            stored_values.get("chunk_overlap"),
            default=defaults.chunk_overlap,
            minimum=0,
        )
    except ValidationError as exception:
        _raise_stored_rag_config_error("chunk_overlap", exception, build_error)
    try:
        validate_chunking_window(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunking_strategy=chunking_strategy,
        )
    except ValidationError as exception:
        _raise_stored_rag_config_error("chunk window", exception, build_error)
    embedding_model = default_embedding_model
    embedding_model_raw = stored_values.get("embedding_model")
    if embedding_model_raw is not None:
        try:
            embedding_model = normalize_rag_embedding_model(embedding_model_raw)
        except ValidationError as exception:
            _raise_stored_rag_config_error("embedding_model", exception, build_error)
    return NormalizedRagConfig(
        enabled=enabled,
        retrieval=NormalizedRagRetrieval(
            strategy=retrieval_strategy,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        ),
        chunking=NormalizedRagChunking(
            strategy=chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ),
        embedding_model=embedding_model,
    )
