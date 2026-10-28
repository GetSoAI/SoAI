"""SoAI - Undefined nonfinite substitutions retained through simplification [backend/core/math/symbolic_simplification_domains.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
from collections.abc import Sequence
from typing import TYPE_CHECKING

from sympy import (
    Add,
    Contains,
    Expr,
    Integer,
    Integral,
    Mod,
    Mul,
    Not,
    Pow,
    Product,
    Rational,
    S,
    Sum,
    Symbol,
    floor,
)

from core.math.symbolic_domain import record_restriction
from core.math.symbolic_operation_domains import BOUNDED_BODY_FUNCTIONS
from core.math.symbolic_values import DomainRestriction, require_expression, require_expressions

if TYPE_CHECKING:
    from core.math.symbolic_values import SymbolicValue

__all__ = ("record_cancelled_operands", "record_function_simplification")

_VALUE_TRANSFORMS = frozenset(
    {"simplify", "expand", "factor", "cancel", "apart", "together", "trigsimp"}
)


def record_cancelled_operands(
    restrictions: list[DomainRestriction],
    operator: ast.operator,
    left: SymbolicValue,
    right: SymbolicValue,
    result: SymbolicValue,
) -> None:
    if not isinstance(left, Expr) or not isinstance(right, Expr) or not isinstance(result, Expr):
        return
    if not left.free_symbols | right.free_symbols:
        return
    original: Expr
    if isinstance(operator, ast.Add | ast.Sub):
        original = Add(left, -right if isinstance(operator, ast.Sub) else right, evaluate=False)
    elif isinstance(operator, ast.Mult):
        original = Mul(left, right, evaluate=False)
    elif isinstance(operator, ast.Div | ast.FloorDiv):
        original = Mul(left, Pow(right, Integer(-1), evaluate=False), evaluate=False)
        if isinstance(operator, ast.FloorDiv):
            original = floor(original, evaluate=False)
    elif isinstance(operator, ast.Mod):
        original = Mod(left, right, evaluate=False)
    elif isinstance(operator, ast.Pow):
        original = Pow(left, right, evaluate=False)
    else:
        return
    _record_nonfinite_substitutions(restrictions, original, result, original.free_symbols)


def record_function_simplification(
    restrictions: list[DomainRestriction],
    name: str,
    arguments: Sequence[SymbolicValue],
    result: SymbolicValue,
) -> None:
    if not arguments or not isinstance(result, Expr):
        return
    original: Expr
    if name in _VALUE_TRANSFORMS and isinstance(arguments[0], Expr):
        original = arguments[0]
    elif (
        name in BOUNDED_BODY_FUNCTIONS and len(arguments) == 4 and isinstance(arguments[1], Symbol)
    ):
        value = require_expression(arguments[0], position=1)
        bounds = (
            arguments[1],
            require_expression(arguments[2], position=3),
            require_expression(arguments[3], position=4),
        )
        if name == "integrate":
            original = Integral(value, bounds)
        elif name == "summation":
            original = Sum(value, bounds)
        else:
            original = Product(value, bounds)
    elif name in ("sum", "prod", "mean", "hypot"):
        values = require_expressions(arguments)
        if name == "prod":
            original = Mul(*values, evaluate=False)
        elif name == "hypot":
            original = Pow(
                Add(*(Pow(value, Integer(2), evaluate=False) for value in values), evaluate=False),
                Rational(1, 2),
                evaluate=False,
            )
        else:
            original = Add(*values, evaluate=False)
            if name == "mean":
                original = Mul(original, Rational(1, len(values)), evaluate=False)
    else:
        return
    symbols = (
        original.free_symbols - result.free_symbols
        if name in BOUNDED_BODY_FUNCTIONS
        else original.free_symbols
    )
    _record_nonfinite_substitutions(restrictions, original, result, symbols)


def _record_nonfinite_substitutions(
    restrictions: list[DomainRestriction], original: Expr, result: Expr, symbols: set[Symbol]
) -> None:
    if original == result:
        return
    for symbol in symbols:
        record_restriction(
            restrictions,
            DomainRestriction(
                term=original,
                zero=symbol,
                condition=Not(Contains(symbol, S.Complexes)),
                nonfinite_bindings=(),
            ),
        )
