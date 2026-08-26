"""SoAI - Numeric extraction helpers for text input [backend/core/validation/text_numbers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import TYPE_CHECKING

from core.validation.numbers import coerce_float_from_json

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "coerce_float_from_text",
    "coerce_int_from_text",
)

_FLOAT_FROM_TEXT_RE_PATTERN: str = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"


@lru_cache(maxsize=1)
def _float_from_text_regex() -> re.Pattern[str]:
    return re.compile(_FLOAT_FROM_TEXT_RE_PATTERN)


def coerce_float_from_text(
    value: JSONValue,
    *,
    default: float | None = None,
    allow_bool: bool = False,
    allow_nonfinite: bool = False,
) -> float | None:
    if isinstance(value, int | float | bool):
        return coerce_float_from_json(
            value,
            default=default,
            allow_bool=allow_bool,
            allow_nonfinite=allow_nonfinite,
        )
    if isinstance(value, str):
        match = _float_from_text_regex().search(value.replace(",", ""))
        if match is None:
            return default
        return coerce_float_from_json(
            match.group(0),
            default=default,
            allow_bool=allow_bool,
            allow_nonfinite=allow_nonfinite,
        )
    return default


def coerce_int_from_text(
    value: JSONValue,
    *,
    default: int | None = None,
    allow_bool: bool = False,
    allow_nonfinite: bool = False,
) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value) if allow_bool else default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if (not allow_nonfinite) and not math.isfinite(value):
            return default
        return int(value)
    if isinstance(value, str):
        match = _float_from_text_regex().search(value.replace(",", ""))
        if match is None:
            return default
        token = match.group(0)
        if "." not in token and "e" not in token.lower():
            try:
                return int(token)
            except ValueError:
                return default
        parsed = coerce_float_from_json(
            token,
            default=None,
            allow_bool=False,
            allow_nonfinite=allow_nonfinite,
        )
        return int(parsed) if parsed is not None else default
    return default
