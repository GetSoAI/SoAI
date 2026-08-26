"""SoAI - Canonical trace and cancellation identifier builders [backend/core/runtime/soai_identifiers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import re
import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = (
    "build_hashed_identifier",
    "build_soai_id",
    "create_prefixed_hex_id",
    "create_request_id",
    "create_system_id",
    "extend_soai_id",
    "normalize_segments",
    "safe_or_hashed_segment",
)

_SAFE_SEGMENT_PATTERN_TEXT = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"


def create_prefixed_hex_id(prefix: str, *, length: int | None = None, separator: str = "_") -> str:
    prefix_value = _normalize_required_segment(prefix, label="prefix")
    if not isinstance(separator, str):
        raise ValidationError("Identifier separator must be a string.")
    separator_value = separator
    if separator_value and re.fullmatch(r"^[A-Za-z0-9._-]{1,8}$", separator_value) is None:
        raise ValidationError("Identifier separator must be a short safe string.")
    suffix = uuid.uuid4().hex
    if length is not None:
        if isinstance(length, bool):
            raise ValidationError("Identifier suffix length must be an integer.")
        if length < 1:
            raise ValidationError("Identifier suffix length must be positive.")
        if length > len(suffix):
            raise ValidationError("Identifier suffix length must be <= 32.")
        suffix = suffix[:length]
    return f"{prefix_value}{separator_value}{suffix}"


def create_request_id(*, prefix: str) -> str:
    prefix_value = _normalize_required_segment(prefix, label="prefix")
    suffix = uuid.uuid4().hex[:12]
    return build_soai_id(("req", prefix_value, suffix))


def create_system_id(
    *,
    subsystem: str,
    owner: str | None = None,
    include_random_suffix: bool,
) -> str:
    subsystem_value = _normalize_required_segment(subsystem, label="subsystem")
    segments: list[str] = ["sys", subsystem_value]
    if owner is not None:
        segments.append(_normalize_required_segment(owner, label="owner"))
    if include_random_suffix:
        segments.append(uuid.uuid4().hex[:12])
    return build_soai_id(tuple(segments))


def build_soai_id(segments: tuple[str, ...]) -> str:
    if not segments:
        raise ValidationError("SoAI identifier requires at least one segment.")
    normalized_segments = [_normalize_required_segment("soai", label="prefix")]
    for segment in segments:
        normalized_segments.append(_normalize_required_segment(segment, label="segment"))
    return "::".join(normalized_segments)


def extend_soai_id(base_id: str, segments: tuple[str, ...]) -> str:
    base = str(base_id or "").strip()
    if not base:
        raise ValidationError("Base identifier is required.")
    if not base.startswith("soai::"):
        raise ValidationError("Base identifier must start with 'soai::'.")
    if not segments:
        return base
    suffix = "::".join(
        _normalize_required_segment(segment, label="segment") for segment in segments
    )
    return f"{base}::{suffix}"


def safe_or_hashed_segment(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValidationError("Identifier segment must be non-empty.")
    if re.fullmatch(_SAFE_SEGMENT_PATTERN_TEXT, normalized) is not None:
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"h_{digest}"


def build_hashed_identifier(label: str, value: str) -> str:
    label_segment = _normalize_required_segment(label, label="label")
    hashed = safe_or_hashed_segment(value)
    return f"{label_segment}_{hashed}"


def normalize_segments(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        normalized.append(_normalize_required_segment(value, label="segment"))
    return tuple(normalized)


def _normalize_required_segment(value: str, *, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValidationError(f"Identifier {label} must be a non-empty string.")
    if "::" in normalized:
        return safe_or_hashed_segment(normalized)
    if re.fullmatch(_SAFE_SEGMENT_PATTERN_TEXT, normalized) is not None:
        return normalized
    return safe_or_hashed_segment(normalized)
