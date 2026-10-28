"""SoAI - Arithmetic operator semantics for sympy values [backend/core/math/symbolic_operators.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from sympy import (
    Eq,
    Expr,
    Ge,
    Gt,
    ImmutableMatrix,
    Integer,
    Le,
    Lt,
    Mod,
    Ne,
    Rational,
    floor,
    nan,
    zoo,
)

from core.math.errors import (
    UNSUPPORTED_COMPARISON_MESSAGE,
    MathDomainError,
    MathExpressionError,
    build_unsupported_element_error,
)
from core.math.exact_integers import exact_integer_power
from core.math.symbolic_values import require_arithmetic

if TYPE_CHECKING:
    from sympy import Basic
    from sympy.logic.boolalg import Boolean

    from core.math.symbolic_values import SymbolicValue

__all__ = (
    "apply_symbolic_binary_operator",
    "apply_symbolic_comparison",
)

_MATRIX_OPERATOR_MESSAGE = "This operator is not supported for matrices"
_UNDEFINED_COMPARISON_MESSAGE = "Comparisons need defined values, but one side is undefined (nan or complex infinity), as in 0/0 or log(0)"


def apply_symbolic_binary_operator(
    operator: ast.operator, left_value: SymbolicValue, right_value: SymbolicValue
) -> Basic:
    left = require_arithmetic(left_value)
    right = require_arithmetic(right_value)
    if isinstance(left, ImmutableMatrix) or isinstance(right, ImmutableMatrix):
        return _apply_matrix_operator(operator, left, right)
    if isinstance(operator, ast.Add):
        return left + right
    if isinstance(operator, ast.Sub):
        return left - right
    if isinstance(operator, ast.Mult):
        return left * right
    if isinstance(operator, ast.Pow):
        return _apply_power(left, right)
    if right.is_zero is True:
        raise MathDomainError(
            "Modulo by zero" if isinstance(operator, ast.Mod) else "Division by zero"
        )
    if isinstance(operator, ast.Div):
        return left / right
    if isinstance(operator, ast.FloorDiv):
        return floor(left / right)
    if isinstance(operator, ast.Mod):
        return Mod(left, right)
    raise build_unsupported_element_error(operator)


def apply_symbolic_comparison(
    operator: ast.cmpop,
    left: Expr | ImmutableMatrix,
    right: Expr | ImmutableMatrix,
) -> Boolean:
    if nan in (left, right) or zoo in (left, right):
        raise MathDomainError(_UNDEFINED_COMPARISON_MESSAGE)
    if isinstance(operator, ast.Eq):
        return Eq(left, right)
    if isinstance(operator, ast.NotEq):
        return Ne(left, right)
    if isinstance(left, ImmutableMatrix) or isinstance(right, ImmutableMatrix):
        raise MathExpressionError("Matrices can only be compared with == or !=")
    if isinstance(operator, ast.Lt):
        return Lt(left, right)
    if isinstance(operator, ast.LtE):
        return Le(left, right)
    if isinstance(operator, ast.Gt):
        return Gt(left, right)
    if isinstance(operator, ast.GtE):
        return Ge(left, right)
    raise MathExpressionError(UNSUPPORTED_COMPARISON_MESSAGE)


def _apply_power(base: Expr, exponent: Expr) -> Expr:
    if base.is_zero is True and exponent.is_negative is True:
        raise MathDomainError("Invalid power operation: zero cannot be raised to a negative power")
    if isinstance(base, Rational) and isinstance(exponent, Integer):
        magnitude = abs(int(exponent))
        numerator = exact_integer_power(int(base.p), magnitude)
        denominator = exact_integer_power(int(base.q), magnitude)
        if int(exponent) < 0:
            return Rational(denominator, numerator)
        return Rational(numerator, denominator)
    return base**exponent


def _apply_matrix_operator(
    operator: ast.operator,
    left: Expr | ImmutableMatrix,
    right: Expr | ImmutableMatrix,
) -> ImmutableMatrix:
    if isinstance(left, ImmutableMatrix) and isinstance(right, ImmutableMatrix):
        if isinstance(operator, ast.Add):
            return left + right
        if isinstance(operator, ast.Sub):
            return left - right
        if isinstance(operator, ast.Mult):
            return left * right
        raise MathExpressionError(_MATRIX_OPERATOR_MESSAGE)
    if isinstance(left, ImmutableMatrix) and isinstance(right, Expr):
        if isinstance(operator, ast.Mult):
            return left * right
        if isinstance(operator, ast.Div):
            if right.is_zero is True:
                raise MathDomainError("Division by zero")
            return left * (1 / right)
        if isinstance(operator, ast.Pow) and isinstance(right, Integer):
            return left**right
        raise MathExpressionError(_MATRIX_OPERATOR_MESSAGE)
    if (
        isinstance(left, Expr)
        and isinstance(right, ImmutableMatrix)
        and isinstance(operator, ast.Mult)
    ):
        return right * left
    raise MathExpressionError(_MATRIX_OPERATOR_MESSAGE)
