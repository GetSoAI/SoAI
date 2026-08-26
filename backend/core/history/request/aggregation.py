"""SoAI - History aggregation normalization [backend/core/history/request/aggregation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "normalize_history_aggregation_candidate",
    "normalize_history_aggregation_or_default",
)


def normalize_history_aggregation_candidate(value: JSONValue, *, default: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def normalize_history_aggregation_or_default(
    value: JSONValue,
    *,
    allowed_values: Collection[str],
    default: str,
) -> str:
    candidate = normalize_history_aggregation_candidate(value, default=default).lower()
    return candidate if candidate in allowed_values else default
