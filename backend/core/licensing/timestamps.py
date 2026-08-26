"""SoAI - Exact licensing UTC timestamp contracts [backend/core/licensing/timestamps.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from datetime import UTC, datetime

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

__all__ = ("parse_licensing_timestamp",)


def parse_licensing_timestamp(value: JSONValue, *, field: str) -> datetime:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None
    ):
        raise ValidationError(f"{field} must be an exact RFC3339 UTC timestamp.")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exception:
        raise ValidationError(f"{field} must be an exact RFC3339 UTC timestamp.") from exception
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValidationError(f"{field} must be an exact RFC3339 UTC timestamp.")
    return parsed
