"""SoAI - Math expression variables [backend/core/math/expression_variables.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import keyword
import math

from core.math.errors import MathExpressionError
from core.validation.integers import is_strict_int

__all__ = ("coerce_variables_map",)


def coerce_variables_map(
    variables: dict[str, int | float | bool] | None,
) -> dict[str, int | float]:
    if variables is None:
        return {}
    if not isinstance(variables, dict):
        raise MathExpressionError("variables must be an object mapping names to numbers")
    resolved: dict[str, int | float] = {}
    for key, raw_value in variables.items():
        name = str(key or "").strip()
        if not name:
            raise MathExpressionError("variables contains an empty name")
        if name.startswith("_") or (not name.isidentifier()) or keyword.iskeyword(name):
            raise MathExpressionError(f"Invalid variable name: {name}")
        if isinstance(raw_value, bool):
            raise MathExpressionError(f"Variable '{name}' must be a number")
        if is_strict_int(raw_value):
            number_value: int | float = int(raw_value)
        elif isinstance(raw_value, float):
            try:
                number_value = float(raw_value)
            except OverflowError as exception:
                raise MathExpressionError(f"Variable '{name}' is too large") from exception
        else:
            raise MathExpressionError(f"Variable '{name}' must be a number")
        try:
            finite_check = float(number_value)
        except OverflowError as exception:
            raise MathExpressionError(f"Variable '{name}' is too large") from exception
        if not math.isfinite(finite_check):
            raise MathExpressionError(f"Variable '{name}' must be finite")
        resolved[name] = number_value
    return resolved
