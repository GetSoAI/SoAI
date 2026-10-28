"""SoAI - Exact integer and combinatorics math functions [backend/core/math/integer_functions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Callable

from core.math.exact_integers import (
    coerce_integral_argument,
    coerce_non_negative_integral_argument,
    ensure_binomial_within_budget,
    ensure_factorial_within_budget,
    ensure_integer_within_budget,
    ensure_permutation_within_budget,
    exact_least_common_multiple,
)

__all__ = ("build_integer_functions",)


def build_integer_functions() -> dict[str, Callable[..., int | float]]:
    return {
        "factorial": _factorial,
        "comb": _combinations,
        "perm": _permutations,
        "gcd": _greatest_common_divisor,
        "lcm": _least_common_multiple,
        "isqrt": _integer_square_root,
    }


def _factorial(value: int | float) -> int:
    count = coerce_non_negative_integral_argument(value, description="n")
    ensure_factorial_within_budget(count)
    return ensure_integer_within_budget(math.factorial(count))


def _combinations(total_value: int | float, chosen_value: int | float) -> int:
    total = coerce_non_negative_integral_argument(total_value, description="n")
    chosen = coerce_non_negative_integral_argument(chosen_value, description="k")
    ensure_binomial_within_budget(total, chosen)
    return ensure_integer_within_budget(math.comb(total, chosen))


def _permutations(total_value: int | float, chosen_value: int | float) -> int:
    total = coerce_non_negative_integral_argument(total_value, description="n")
    chosen = coerce_non_negative_integral_argument(chosen_value, description="k")
    ensure_permutation_within_budget(total, chosen)
    return ensure_integer_within_budget(math.perm(total, chosen))


def _greatest_common_divisor(*values: int | float) -> int:
    return math.gcd(
        *(coerce_integral_argument(value, description="each value") for value in values)
    )


def _least_common_multiple(*values: int | float) -> int:
    return exact_least_common_multiple(
        coerce_integral_argument(value, description="each value") for value in values
    )


def _integer_square_root(value: int | float) -> int:
    return math.isqrt(coerce_non_negative_integral_argument(value, description="n"))
