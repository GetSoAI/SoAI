"""SoAI - OpenAI text truncation markers [backend/core/openai/truncation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.validation.integers import require_non_negative_exact_int

__all__ = (
    "SOAI_TRUNCATION_MARKER",
    "SOAI_TRUNCATION_MARKER_TEXT",
    "build_marker_truncation_text",
    "build_prefix_truncation_text",
)

SOAI_TRUNCATION_MARKER: str = "\n[SOAI_TRUNCATED]\n"
SOAI_TRUNCATION_MARKER_TEXT: str = "SOAI_TRUNCATED"


def build_prefix_truncation_text(*, original: str, prefix_length: int) -> str:
    normalized_prefix_length = require_non_negative_exact_int(
        prefix_length,
        type_message="prefix_length must be an integer.",
        range_message="prefix_length must be non-negative.",
    )
    prefix = original[:normalized_prefix_length]
    if normalized_prefix_length >= len(original):
        return prefix
    return f"{prefix}{SOAI_TRUNCATION_MARKER}"


def build_marker_truncation_text(*, original: str, max_total_chars: int) -> str:
    normalized_max_chars = require_non_negative_exact_int(
        max_total_chars,
        type_message="max_total_chars must be an integer.",
        range_message="max_total_chars must be non-negative.",
    )
    if normalized_max_chars <= 0:
        return ""
    if len(original) <= normalized_max_chars:
        return original
    if normalized_max_chars <= len(SOAI_TRUNCATION_MARKER):
        return original[:normalized_max_chars]
    head = original[: normalized_max_chars - len(SOAI_TRUNCATION_MARKER)].rstrip()
    return f"{head}{SOAI_TRUNCATION_MARKER}"
