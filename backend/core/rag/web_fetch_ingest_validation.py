"""SoAI - Web fetch ingest job parameter validation [backend/core/rag/web_fetch_ingest_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.rag.parameter_validation import (
    normalize_chunking_strategy,
    normalize_retrieval_strategy,
    normalize_return_extract_mode,
    validate_return_max_chars,
    validate_similarity_threshold,
    validate_top_k,
)
from core.types.json import JSONValue
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_int, require_non_empty_str

__all__ = (
    "require_web_fetch_chunking_strategy",
    "require_web_fetch_int",
    "require_web_fetch_non_empty_str",
    "require_web_fetch_retrieval_strategy",
    "require_web_fetch_return_extract_mode",
    "require_web_fetch_return_max_chars",
    "require_web_fetch_similarity_threshold",
    "require_web_fetch_top_k",
    "resolve_web_fetch_focus_query",
    "resolve_web_fetch_user_id",
)


def require_web_fetch_non_empty_str(raw: JSONValue | None, message: str) -> str:
    return require_non_empty_str(
        raw,
        label="web_fetch_ingest",
        build_error=ValidationError,
        invalid_message=message,
    )


def require_web_fetch_int(raw: JSONValue | None, message: str) -> int:
    return require_int(
        raw,
        label="web_fetch_ingest",
        build_error=ValidationError,
        invalid_message=message,
    )


def resolve_web_fetch_focus_query(raw: JSONValue | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    raise ValidationError("Job has invalid focus_query for web_fetch_ingest")


def require_web_fetch_retrieval_strategy(raw: JSONValue | None) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationError("Job missing valid retrieval_strategy for web_fetch_ingest")
    return normalize_retrieval_strategy(raw)


def require_web_fetch_top_k(raw: JSONValue | None, max_top_k: int) -> int:
    if not is_strict_int(raw):
        raise ValidationError("Job missing valid top_k for web_fetch_ingest")
    top_k = validate_top_k(raw)
    if top_k > max_top_k:
        raise ValidationError(f"top_k must be between 1 and {max_top_k}")
    return top_k


def require_web_fetch_similarity_threshold(raw: JSONValue | None) -> float:
    if not isinstance(raw, int | float) or isinstance(raw, bool):
        raise ValidationError("Job missing valid similarity_threshold for web_fetch_ingest")
    return validate_similarity_threshold(raw)


def require_web_fetch_chunking_strategy(raw: JSONValue | None) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationError("Job missing valid chunking_strategy for web_fetch_ingest")
    return normalize_chunking_strategy(raw)


def require_web_fetch_return_extract_mode(raw: JSONValue | None) -> str:
    if raw is None:
        return "markdown"
    if isinstance(raw, str) and raw.strip():
        return normalize_return_extract_mode(raw)
    raise ValidationError("Job missing valid return_extract_mode for web_fetch_ingest")


def require_web_fetch_return_max_chars(raw: JSONValue | None) -> int:
    if not is_strict_int(raw):
        raise ValidationError("Job missing valid return_max_chars for web_fetch_ingest")
    return validate_return_max_chars(raw)


def resolve_web_fetch_user_id(raw: JSONValue | None) -> int:
    if not is_strict_int(raw) or raw < 0:
        raise ValidationError("Job missing valid user_id for web_fetch_ingest")
    return raw
