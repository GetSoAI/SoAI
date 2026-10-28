"""SoAI - Math expression variables [backend/core/math/expression_variables.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import keyword
import math
import unicodedata
from collections.abc import Collection
from typing import TYPE_CHECKING

from core.math.errors import MathExpressionError
from core.math.expression_limits import MAX_INTEGER_BITS, MAX_VARIABLES
from core.math.expression_parsing import validate_assignment_name
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("coerce_variables_map",)


def coerce_variables_map(
    variables: JSONValue | None,
    *,
    reserved_names: Collection[str] = (),
) -> dict[str, int | float]:
    if variables is None:
        return {}
    if not isinstance(variables, dict):
        raise MathExpressionError("variables must be an object mapping names to numbers")
    if len(variables) > MAX_VARIABLES:
        raise MathExpressionError(f"variables may contain at most {MAX_VARIABLES} entries")
    resolved: dict[str, int | float] = {}
    for key, raw_value in variables.items():
        name = unicodedata.normalize("NFKC", str(key or "").strip())
        if not name:
            raise MathExpressionError("variables contains an empty name")
        if (not name.isidentifier()) or keyword.iskeyword(name):
            raise MathExpressionError(f"Invalid variable name: {name}")
        validate_assignment_name(name, reserved_names=reserved_names)
        if name in resolved:
            raise MathExpressionError(f"variables contains the name '{name}' more than once")
        resolved[name] = _coerce_variable_value(name, raw_value)
    return resolved


def _coerce_variable_value(name: str, raw_value: JSONValue) -> int | float:
    if isinstance(raw_value, bool):
        raise MathExpressionError(f"Variable '{name}' must be a number")
    if is_strict_int(raw_value):
        if raw_value.bit_length() > MAX_INTEGER_BITS:
            raise MathExpressionError(
                f"Variable '{name}' is too large: exact integers are limited to {MAX_INTEGER_BITS} bits"
            )
        return int(raw_value)
    if not isinstance(raw_value, float):
        raise MathExpressionError(f"Variable '{name}' must be a number")
    try:
        number = float(raw_value)
    except OverflowError as exception:
        raise MathExpressionError(f"Variable '{name}' is too large") from exception
    if not math.isfinite(number):
        raise MathExpressionError(f"Variable '{name}' must be finite")
    return number
