"""SoAI - Numeric operator semantics for math evaluation [backend/core/math/numeric_operators.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
import math
from fractions import Fraction
from typing import TYPE_CHECKING

from core.math.errors import (
    UNSUPPORTED_COMPARISON_MESSAGE,
    MathExpressionError,
    build_unsupported_element_error,
)
from core.math.exact_integers import ensure_integer_within_budget, exact_integer_power
from core.math.real_functions import floating_sign, real_power
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.math.program_evaluation import MathValue

__all__ = (
    "BOOLEAN_ARITHMETIC_MESSAGE",
    "apply_binary_operator",
    "apply_comparison",
    "apply_unary_operator",
    "ensure_finite_number",
    "require_condition",
    "require_number",
)

BOOLEAN_ARITHMETIC_MESSAGE = (
    "Booleans are not allowed in arithmetic; use a conditional such as (1 if x > 0 else 0)"
)
_CONDITION_MESSAGE = "Conditions must be true/false values such as x > 0; and, or, not and if-else do not accept numbers"


def ensure_finite_number(value: int | float) -> int | float:
    if is_strict_int(value):
        return ensure_integer_within_budget(value)
    if not math.isfinite(value):
        raise MathExpressionError("Result is not a finite number")
    return value


def require_condition(value: MathValue) -> bool:
    if not isinstance(value, bool):
        raise MathExpressionError(_CONDITION_MESSAGE)
    return value


def apply_unary_operator(operator: ast.unaryop, operand: MathValue) -> MathValue:
    if isinstance(operator, ast.Not):
        return not require_condition(operand)
    number = require_number(operand)
    if isinstance(operator, ast.UAdd):
        return number
    if isinstance(operator, ast.USub):
        return -number
    raise build_unsupported_element_error(operator)


def apply_binary_operator(
    operator: ast.operator,
    left: MathValue,
    right: MathValue,
) -> int | float:
    left_number = require_number(left)
    right_number = require_number(right)
    try:
        result = _apply_arithmetic(operator, left_number, right_number)
    except OverflowError as exception:
        raise MathExpressionError("Result is too large") from exception
    return ensure_finite_number(result)


def apply_comparison(operator: ast.cmpop, left: MathValue, right: MathValue) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        raise MathExpressionError(
            "Booleans cannot be compared; combine conditions with and/or instead"
        )
    if isinstance(operator, ast.Lt):
        return left < right
    if isinstance(operator, ast.LtE):
        return left <= right
    if isinstance(operator, ast.Gt):
        return left > right
    if isinstance(operator, ast.GtE):
        return left >= right
    if isinstance(operator, ast.Eq):
        return left == right
    if isinstance(operator, ast.NotEq):
        return left != right
    raise MathExpressionError(UNSUPPORTED_COMPARISON_MESSAGE)


def require_number(value: MathValue) -> int | float:
    if isinstance(value, bool):
        raise MathExpressionError(BOOLEAN_ARITHMETIC_MESSAGE)
    return value


def _apply_arithmetic(operator: ast.operator, left: int | float, right: int | float) -> int | float:
    mixed_types = isinstance(left, float) != isinstance(right, float)
    wide_integer = any(
        is_strict_int(value) and value.bit_length() > 1023 for value in (left, right)
    )
    if mixed_types and wide_integer and not isinstance(operator, ast.Pow):
        return _mixed_arithmetic(operator, left, right)
    if isinstance(operator, ast.Add):
        return left + right
    if isinstance(operator, ast.Sub):
        return left - right
    if isinstance(operator, ast.Mult):
        return left * right
    if isinstance(operator, ast.Div):
        if right == 0:
            raise MathExpressionError("Division by zero")
        return left / right
    if isinstance(operator, ast.FloorDiv):
        if right == 0:
            raise MathExpressionError("Division by zero")
        return left // right
    if isinstance(operator, ast.Mod):
        if right == 0:
            raise MathExpressionError("Modulo by zero")
        return left % right
    if isinstance(operator, ast.Pow):
        return _apply_power(left, right)
    raise build_unsupported_element_error(operator)


def _mixed_arithmetic(operator: ast.operator, left: int | float, right: int | float) -> float:
    first, second = Fraction(left), Fraction(right)
    if isinstance(operator, ast.Add):
        return float(first + second)
    if isinstance(operator, ast.Sub):
        return float(first - second)
    signed_zero = math.copysign(0.0, floating_sign(left) * floating_sign(right))
    if isinstance(operator, ast.Mult):
        if left == 0 or right == 0:
            return signed_zero
        return float(first * second)
    if not isinstance(operator, ast.Div | ast.FloorDiv | ast.Mod):
        raise build_unsupported_element_error(operator)
    if right == 0:
        raise MathExpressionError(
            "Modulo by zero" if isinstance(operator, ast.Mod) else "Division by zero"
        )
    if isinstance(operator, ast.Div):
        if left == 0:
            return signed_zero
        return float(first / second)
    if isinstance(operator, ast.FloorDiv):
        quotient = float(first // second)
        return signed_zero if quotient == 0 else quotient
    if isinstance(operator, ast.Mod):
        result = float(first % second)
        return math.copysign(0.0, floating_sign(right)) if result == 0 else result
    raise build_unsupported_element_error(operator)


def _apply_power(base: int | float, exponent: int | float) -> int | float:
    if is_strict_int(base) and is_strict_int(exponent) and exponent >= 0:
        return exact_integer_power(base, exponent)
    if exponent == 0 or base == 1:
        return 1.0
    if base == 0 and exponent < 0:
        raise MathExpressionError(
            "Invalid power operation: zero cannot be raised to a negative power"
        )
    if base < 0 and isinstance(exponent, float) and not exponent.is_integer():
        raise MathExpressionError(
            "Invalid power operation: a negative base with a fractional exponent has no real result; use cbrt(x) for cube roots"
        )
    if base == 0 and exponent > 0:
        return math.copysign(0.0, base) if exponent % 2 == 1 else 0.0
    if base == -1:
        return -1.0 if exponent % 2 else 1.0
    try:
        return real_power(base, exponent)
    except OverflowError as exception:
        raise MathExpressionError(
            "Invalid power operation: the result is outside the floating-point range"
        ) from exception
