"""SoAI - Document reading input validation [backend/files/parsers/document_reading_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.validation.numbers import coerce_float_from_json
from core.validation.requirements import (
    require_non_negative_exact_int,
    require_positive_exact_int,
)
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "NormalizedDocumentReadInputs",
    "normalize_document_read_inputs",
)


@dataclass(frozen=True, slots=True)
class NormalizedDocumentReadInputs:
    file_path: str
    parse_timeout_sec: float
    max_chars: int
    offset_chars: int


def normalize_document_read_inputs(
    *,
    file_path: str,
    parse_timeout_sec: float,
    max_chars: int,
    offset_chars: int,
) -> NormalizedDocumentReadInputs:
    normalized_file_path = _normalize_file_path(file_path)
    normalized_timeout = _normalize_timeout(parse_timeout_sec)
    normalized_max_chars = require_positive_exact_int(
        max_chars,
        type_message="max_chars must be an integer",
        range_message="max_chars must be > 0",
    )
    normalized_offset_chars = require_non_negative_exact_int(
        offset_chars,
        type_message="offset_chars must be an integer",
        range_message="offset_chars must be >= 0",
    )
    return NormalizedDocumentReadInputs(
        file_path=normalized_file_path,
        parse_timeout_sec=normalized_timeout,
        max_chars=normalized_max_chars,
        offset_chars=normalized_offset_chars,
    )


def _normalize_file_path(value: str) -> str:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        raise ValidationError("file_path must be a non-empty string")
    return normalized


def _normalize_timeout(value: float) -> float:
    normalized = coerce_float_from_json(value, default=None)
    if normalized is None:
        raise ValidationError("parse_timeout_sec must be a number")
    if normalized <= 0:
        raise ValidationError("parse_timeout_sec must be > 0")
    return normalized
