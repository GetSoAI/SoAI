"""SoAI - Exact integer size policy for math evaluation [backend/core/math/exact_integers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Iterable
from decimal import Decimal

from core.math.errors import MathExpressionError
from core.math.expression_limits import MAX_INTEGER_BITS
from core.validation.integers import is_strict_int

__all__ = (
    "integer_budget_error",
    "coerce_integral_argument",
    "coerce_non_negative_integral_argument",
    "ensure_binomial_within_budget",
    "ensure_factorial_within_budget",
    "ensure_integer_within_budget",
    "ensure_permutation_within_budget",
    "exact_decimal_ratio",
    "exact_integer_power",
    "exact_least_common_multiple",
)

_RESULT_SUBJECT = "Result is too large"
_POWER_SUBJECT = "Invalid power operation"
_ESTIMATE_SLACK_BITS = 64
_MAX_ESTIMATED_ARGUMENT_BITS = 32


def integer_budget_error(subject: str) -> MathExpressionError:
    return MathExpressionError(f"{subject}: exact integers are limited to {MAX_INTEGER_BITS} bits")


def ensure_integer_within_budget(value: int, *, subject: str = _RESULT_SUBJECT) -> int:
    if value.bit_length() > MAX_INTEGER_BITS:
        raise integer_budget_error(subject)
    return value


def exact_decimal_ratio(token: str) -> tuple[int, int]:
    number = Decimal(token)
    digits_and_exponent = number.as_tuple()
    exponent = digits_and_exponent.exponent
    if not isinstance(exponent, int):
        raise MathExpressionError("Numbers must be finite")
    if (len(digits_and_exponent.digits) + abs(exponent)) * math.log2(10) > MAX_INTEGER_BITS:
        raise integer_budget_error("Number has too many digits")
    return number.as_integer_ratio()


def exact_integer_power(base: int, exponent: int) -> int:
    magnitude_bits = abs(base).bit_length()
    if magnitude_bits > 1 and exponent * (magnitude_bits - 1) >= MAX_INTEGER_BITS:
        raise integer_budget_error(_POWER_SUBJECT)
    return ensure_integer_within_budget(base**exponent, subject=_POWER_SUBJECT)


def exact_least_common_multiple(values: Iterable[int]) -> int:
    result = 1
    for value in values:
        result = ensure_integer_within_budget(math.lcm(result, value))
    return result


def ensure_factorial_within_budget(count: int) -> None:
    if count.bit_length() > _MAX_ESTIMATED_ARGUMENT_BITS:
        raise integer_budget_error(_RESULT_SUBJECT)
    if _estimated_factorial_bits(count) > MAX_INTEGER_BITS + _ESTIMATE_SLACK_BITS:
        raise integer_budget_error(_RESULT_SUBJECT)


def ensure_binomial_within_budget(total: int, chosen: int) -> None:
    smaller = min(chosen, total - chosen)
    if smaller <= 0:
        return
    bits_per_choice = total.bit_length() - 1 - smaller.bit_length()
    if max(smaller, smaller * bits_per_choice) > MAX_INTEGER_BITS:
        raise integer_budget_error(_RESULT_SUBJECT)


def ensure_permutation_within_budget(total: int, chosen: int) -> None:
    if chosen <= 0 or chosen > total:
        return
    ensure_factorial_within_budget(chosen)
    if chosen * ((total - chosen + 1).bit_length() - 1) > MAX_INTEGER_BITS:
        raise integer_budget_error(_RESULT_SUBJECT)


def coerce_non_negative_integral_argument(value: int | float, *, description: str) -> int:
    integer = coerce_integral_argument(value, description=description)
    if integer < 0:
        raise ValueError(f"{description} must be a non-negative integer")
    return integer


def coerce_integral_argument(value: int | float, *, description: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{description} must be an integer")
    if is_strict_int(value):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"{description} must be an integer")


def _estimated_factorial_bits(count: int) -> float:
    return math.lgamma(count + 1) / math.log(2)
