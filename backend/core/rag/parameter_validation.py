"""SoAI - Canonical RAG parameter validation helpers [backend/core/rag/parameter_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

from core.errors.exceptions import ValidationError
from core.rag.option_contracts import (
    VALID_CHUNKING_STRATEGIES,
    VALID_RETRIEVAL_STRATEGIES,
    VALID_RETURN_EXTRACT_MODES,
)
from core.validation.integers import (
    is_non_negative_strict_int,
    is_positive_strict_int,
    is_strict_int,
)

__all__ = (
    "VALID_CHUNKING_STRATEGIES",
    "VALID_RETRIEVAL_STRATEGIES",
    "VALID_RETURN_EXTRACT_MODES",
    "coerce_chunking_strategy",
    "normalize_chunking_strategy",
    "normalize_retrieval_strategy",
    "normalize_return_extract_mode",
    "validate_chunking_window",
    "validate_finite_float",
    "validate_non_negative_finite_float",
    "validate_return_max_chars",
    "validate_similarity_threshold",
    "validate_top_k",
)


def normalize_retrieval_strategy(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized not in VALID_RETRIEVAL_STRATEGIES:
        raise ValidationError(
            f"retrieval_strategy must be one of: {', '.join(VALID_RETRIEVAL_STRATEGIES)}",
        )
    return normalized


def coerce_chunking_strategy(value: str | None) -> str:
    if value is None:
        return "token_based"
    normalized = str(value or "").strip()
    if not normalized:
        return "token_based"
    if normalized not in VALID_CHUNKING_STRATEGIES:
        raise ValidationError(
            f"chunking_strategy must be one of: {', '.join(VALID_CHUNKING_STRATEGIES)}",
        )
    return normalized


def normalize_chunking_strategy(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValidationError("chunking_strategy must be a non-empty string")
    if normalized not in VALID_CHUNKING_STRATEGIES:
        raise ValidationError(
            f"chunking_strategy must be one of: {', '.join(VALID_CHUNKING_STRATEGIES)}",
        )
    return normalized


def validate_chunking_window(
    *,
    chunk_size: int,
    chunk_overlap: int,
    chunking_strategy: str,
) -> None:
    if not is_positive_strict_int(chunk_size):
        raise ValidationError(f"chunk_size must be positive, got {chunk_size}")
    if not is_non_negative_strict_int(chunk_overlap):
        raise ValidationError(f"chunk_overlap must be non-negative, got {chunk_overlap}")
    if chunking_strategy not in VALID_CHUNKING_STRATEGIES:
        raise ValidationError(
            f"Invalid chunking_strategy: {chunking_strategy}. Valid: {VALID_CHUNKING_STRATEGIES}",
        )
    if chunking_strategy in ("token_based", "fixed_size") and chunk_overlap >= chunk_size:
        raise ValidationError(
            f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size}) for strategy {chunking_strategy}",
        )


def validate_top_k(value: int) -> int:
    if not is_strict_int(value) or value < 1:
        raise ValidationError("top_k must be an integer >= 1.")
    return value


def validate_finite_float(value: float, *, field_name: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValidationError(f"{field_name} must be a finite number.")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValidationError(f"{field_name} must be finite.")
    return parsed


def validate_non_negative_finite_float(value: float, *, field_name: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValidationError(f"{field_name} must be a non-negative finite number.")
    parsed = validate_finite_float(float(value), field_name=field_name)
    if parsed < 0.0:
        raise ValidationError(f"{field_name} must be a non-negative finite number.")
    return parsed


def validate_similarity_threshold(value: float) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValidationError("similarity_threshold must be a number in [0.0, 1.0].")
    threshold = validate_finite_float(float(value), field_name="similarity_threshold")
    if threshold < 0.0 or threshold > 1.0:
        raise ValidationError("similarity_threshold must be between 0.0 and 1.0.")
    return threshold


def normalize_return_extract_mode(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in VALID_RETURN_EXTRACT_MODES:
        raise ValidationError("return_extract_mode must be 'markdown', 'text', or 'html'")
    return normalized


def validate_return_max_chars(value: int) -> int:
    if not is_strict_int(value):
        raise ValidationError("return_max_chars must be an integer")
    max_chars = int(value)
    if max_chars < 1000 or max_chars > 500000:
        raise ValidationError("return_max_chars must be between 1000 and 500000")
    return max_chars
