"""SoAI - Summation and statistics math functions [backend/core/math/statistics_functions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import statistics
from collections.abc import Callable
from fractions import Fraction

from core.math.errors import MathExpressionError
from core.math.numeric_operators import ensure_finite_number
from core.math.real_functions import floating_sign
from core.validation.integers import is_strict_int

__all__ = ("build_statistics_functions",)


def build_statistics_functions() -> dict[str, Callable[..., int | float]]:
    return {
        "sum": _sum,
        "prod": _product,
        "mean": _mean,
        "median": _median,
        "stdev": _sample_standard_deviation,
        "pstdev": _population_standard_deviation,
        "variance": _sample_variance,
        "pvariance": _population_variance,
    }


def _sum(*values: int | float) -> int | float:
    integers = [value for value in values if is_strict_int(value)]
    if len(integers) == len(values):
        return ensure_finite_number(sum(integers))
    return float(sum(Fraction(value) for value in values))


def _product(*values: int | float) -> int | float:
    if all(is_strict_int(value) for value in values):
        return ensure_finite_number(math.prod(values))
    result = Fraction(1)
    sign = 1.0
    for value in values:
        result *= Fraction(value)
        sign *= floating_sign(value)
    try:
        return float(result) if result else math.copysign(0.0, sign)
    except OverflowError as exception:
        raise MathExpressionError("Result is not a finite number") from exception


def _mean(*values: int | float) -> int | float:
    return statistics.mean(values)


def _median(*values: int | float) -> int | float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    lower, upper = ordered[middle - 1], ordered[middle]
    if lower == upper == 0:
        return (lower + upper) / 2
    return float((Fraction(lower) + Fraction(upper)) / 2)


def _sample_standard_deviation(*values: int | float) -> float:
    return statistics.stdev(values)


def _population_standard_deviation(*values: int | float) -> float:
    return statistics.pstdev(values)


def _sample_variance(*values: int | float) -> int | float:
    return statistics.variance(values)


def _population_variance(*values: int | float) -> int | float:
    return statistics.pvariance(values)
