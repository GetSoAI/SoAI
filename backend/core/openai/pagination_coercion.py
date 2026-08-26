"""SoAI - OpenAI pagination numeric coercion [backend/core/openai/pagination_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.coercion import coerce_int_from_scalar

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "coerce_openai_int",
    "coerce_openai_optional_int",
    "coerce_openai_pagination_limit",
)


def coerce_openai_optional_int(value: JSONValue) -> int | None:
    return coerce_int_from_scalar(value)


def coerce_openai_int(value: JSONValue, *, default: int) -> int:
    parsed = coerce_openai_optional_int(value)
    return int(default) if parsed is None else parsed


def coerce_openai_pagination_limit(
    value: JSONValue,
    *,
    default: int,
    maximum: int,
) -> int:
    resolved_limit = coerce_openai_int(value, default=default)
    if resolved_limit <= 0:
        resolved_limit = int(default)
    return min(resolved_limit, int(maximum))
