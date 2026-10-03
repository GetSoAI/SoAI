"""SoAI - History sample availability request contract [backend/core/history/request/availability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.record_fields import require_optional_bool

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "HistoryAvailabilityQuery",
    "parse_include_availability",
)


@dataclass(frozen=True, slots=True)
class HistoryAvailabilityQuery:
    retention_hours: int
    metric: str


def parse_include_availability(value: JSONValue) -> bool:
    return (
        require_optional_bool(
            value,
            label="include_availability",
            build_error=ValidationError,
            invalid_message="include_availability must be a boolean",
        )
        is True
    )
