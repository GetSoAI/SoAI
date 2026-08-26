"""SoAI - Task registry configuration normalization helpers [backend/tasks/registry/owner_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.requirements import require_positive_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("normalize_owner_type_limits",)


def normalize_owner_type_limits(raw_limits: Mapping[str, JSONValue]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for owner_type, limit in raw_limits.items():
        normalized_owner_type = str(owner_type or "").strip()
        if not normalized_owner_type:
            raise ValidationError("max_concurrent_by_owner_type owner_type must be non-empty.")
        if isinstance(limit, bool):
            raise ValidationError(
                f"max_concurrent_by_owner_type[{normalized_owner_type}] must be an int.",
            )
        resolved_limit = require_positive_int(
            limit,
            name=f"max_concurrent_by_owner_type[{normalized_owner_type}]",
        )
        normalized[normalized_owner_type] = resolved_limit
    return normalized
