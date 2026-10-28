"""SoAI - Domains introduced by symbolic operations [backend/core/math/symbolic_operation_domains.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from sympy import (
    Abs,
    Contains,
    Expr,
    Gt,
    ImmutableMatrix,
    Integer,
    Lt,
    Max,
    Min,
    Mod,
    Ne,
    Not,
    Piecewise,
    Pow,
    Rel,
    S,
    Symbol,
    atan,
    atan2,
    atanh,
    ceiling,
    cos,
    cosh,
    factorial,
    false,
    floor,
    gamma,
    im,
    log,
    oo,
    sign,
    tan,
    tanh,
    true,
)
from sympy.logic.boolalg import And, Boolean

from core.math.errors import MathDomainError
from core.math.symbolic_domain import (
    extend_restrictions,
    record_restriction,
    region_restriction,
)
from core.math.symbolic_piecewise_forms import polynomial_combinatorics, real_piecewise
from core.math.symbolic_undefined import finite_complex_condition
from core.math.symbolic_values import DomainRestriction, require_expression, require_matrix

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from core.math.symbolic_values import SymbolicValue

__all__ = (
    "BOUNDED_BODY_FUNCTIONS",
    "bound_body_reachability",
    "record_calculus_restrictions",
    "record_comparison_restrictions",
    "record_function_restriction",
    "record_operator_restriction",
    "record_generated_restrictions",
)

_LOGARITHMS = frozenset({"ln", "log", "log10", "log2"})
BOUNDED_BODY_FUNCTIONS = frozenset({"integrate", "summation", "product"})


def bound_body_reachability(name: str, arguments: Sequence[SymbolicValue]) -> Boolean:
    low = require_expression(arguments[2], position=3)
    high = require_expression(arguments[3], position=4)
    if name != "integrate" and (low.is_finite is False or high.is_finite is False):
        return true
    return Ne(high, low if name == "integrate" else low - 1)


def record_operator_restriction(
    restrictions: list[DomainRestriction],
    operator: ast.operator,
    left: SymbolicValue,
    right: SymbolicValue,
) -> None:
    if isinstance(operator, ast.Div | ast.FloorDiv | ast.Mod) and isinstance(right, Expr):
        record_restriction(restrictions, DomainRestriction(term=1 / right, zero=right))
        return
    if not isinstance(operator, ast.Pow) or not isinstance(right, Expr):
        return
    if (
        isinstance(left, ImmutableMatrix)
        and isinstance(right, Integer)
        and right.is_negative is True
    ):
        _record_inverse(restrictions, left)
    elif isinstance(left, Expr) and right.is_nonnegative is not True:
        try:
            negative = true if right.is_negative is True else Lt(right, Integer(0))
        except TypeError:
            negative = true
        if isinstance(negative, Rel):
            negative = negative.canonical
        record_restriction(
            restrictions, DomainRestriction(term=left**right, zero=left, condition=negative)
        )


def record_function_restriction(
    restrictions: list[DomainRestriction], name: str, arguments: Sequence[SymbolicValue]
) -> None:
    if name in ("summation", "product") and len(arguments) == 4:
        low, high = arguments[2:]
        if (
            isinstance(low, Expr)
            and isinstance(high, Expr)
            and low not in (oo, -oo)
            and high not in (oo, -oo)
        ):
            requirement = Contains(high - low, S.Integers)
            if requirement == false:
                raise ValueError("finite summation and product bounds must differ by an integer")
            record_restriction(restrictions, region_restriction(Not(requirement)))
    if name in ("min", "max", "clamp"):
        _record_real_arguments(restrictions, arguments)
    if name in ("comb", "perm"):
        for value in arguments:
            if isinstance(value, Expr) and value.free_symbols:
                pole_marker = 1 / gamma(value + 1)
                record_restriction(
                    restrictions,
                    DomainRestriction(term=pole_marker, zero=pole_marker),
                )
    argument = arguments[0] if arguments else None
    if isinstance(argument, ImmutableMatrix):
        if name == "inv":
            _record_inverse(restrictions, argument)
        elif name in ("det", "rank", "eigenvals"):
            if name != "rank":
                require_matrix(argument, position=1, square=True)
            _record_matrix_field(restrictions, argument)
            if name == "rank":
                _record_matrix_field(restrictions, argument.free_symbols)
        return
    if not isinstance(argument, Expr):
        return
    second = arguments[1] if len(arguments) > 1 else None
    if name in _LOGARITHMS:
        record_restriction(restrictions, DomainRestriction(term=log(argument), zero=argument))
        if isinstance(second, Expr):
            record_restriction(restrictions, DomainRestriction(term=log(second), zero=second))
            record_restriction(
                restrictions, DomainRestriction(term=1 / log(second), zero=log(second))
            )
    elif name == "tan":
        record_restriction(restrictions, DomainRestriction(term=tan(argument), zero=cos(argument)))
    elif name == "tanh":
        record_restriction(
            restrictions, DomainRestriction(term=tanh(argument), zero=cosh(argument))
        )
    elif name == "atan":
        record_restriction(
            restrictions, DomainRestriction(term=atan(argument), zero=argument**2 + 1)
        )
    elif name == "atanh":
        record_restriction(
            restrictions, DomainRestriction(term=atanh(argument), zero=argument**2 - 1)
        )
    elif name == "atan2" and isinstance(second, Expr):
        record_restriction(
            restrictions,
            DomainRestriction(term=atan2(argument, second), zero=argument**2 + second**2),
        )
    elif name == "gamma" and argument.free_symbols:
        record_restriction(
            restrictions, DomainRestriction(term=gamma(argument), zero=1 / gamma(argument))
        )
    elif name == "clamp" and len(arguments) == 3:
        _record_bound_order(restrictions, arguments[1], arguments[2])
    elif name == "factorial" and argument.free_symbols:
        record_restriction(
            restrictions,
            DomainRestriction(term=factorial(argument), zero=1 / gamma(argument + 1)),
        )


def _record_bound_order(
    restrictions: list[DomainRestriction], low: SymbolicValue, high: SymbolicValue
) -> None:
    if not (isinstance(low, Expr) and isinstance(high, Expr)):
        return
    try:
        reversed_bounds = Gt(low - high, Integer(0)) if (low - high).is_number else Gt(low, high)
    except TypeError:
        return
    if reversed_bounds not in (true, false):
        record_restriction(restrictions, region_restriction(reversed_bounds))


def _record_inverse(restrictions: list[DomainRestriction], matrix: ImmutableMatrix) -> None:
    require_matrix(matrix, position=1, square=True)
    _record_matrix_field(restrictions, matrix)
    if matrix.free_symbols:
        determinant = matrix.det()
        record_restriction(
            restrictions,
            DomainRestriction(term=Pow(determinant, Integer(-1), evaluate=False), zero=determinant),
        )


def _record_matrix_field(restrictions: list[DomainRestriction], values: Iterable[Expr]) -> None:
    for entry in values:
        membership = finite_complex_condition(entry)
        if membership == false:
            raise MathDomainError(
                "Matrix algebra requires finite, defined scalar entries; substitute finite values first"
            )
        record_restriction(restrictions, region_restriction(Not(membership)))


def record_calculus_restrictions(
    restrictions: list[DomainRestriction], arguments: Sequence[SymbolicValue], result: SymbolicValue
) -> None:
    expression, variable = arguments[:2]
    if (
        not isinstance(expression, Expr)
        or not isinstance(variable, Symbol)
        or not isinstance(result, Expr)
    ):
        return
    nonanalytic = expression.atoms(Abs, sign, Min, Max, floor, ceiling, Mod)
    prepared = polynomial_combinatorics(expression)
    ordered_branches = any(
        variable in branch.cond.free_symbols
        and any(relation.rel_op not in ("==", "!=") for relation in branch.cond.atoms(Rel))
        for piece in expression.atoms(Piecewise)
        for branch in piece.args
    )
    if (
        any(variable in term.free_symbols for term in nonanalytic)
        or ordered_branches
        or real_piecewise(prepared, variable) != prepared
    ):
        record_restriction(restrictions, region_restriction(Not(Contains(variable, S.Reals))))
    record_generated_restrictions(restrictions, result)


def record_generated_restrictions(restrictions: list[DomainRestriction], value: Expr) -> None:
    if isinstance(value, Piecewise):
        reached: Boolean = true
        for branch in value.args:
            branch_domains: list[DomainRestriction] = []
            record_generated_restrictions(branch_domains, branch.expr)
            extend_restrictions(restrictions, branch_domains, condition=And(reached, branch.cond))
            reached = And(reached, Not(branch.cond))
        return
    if isinstance(value, Pow):
        record_operator_restriction(restrictions, ast.Pow(), value.base, value.exp)
    elif isinstance(value, log):
        record_function_restriction(restrictions, "ln", list(value.args))
    for argument in value.args:
        if isinstance(argument, Expr):
            record_generated_restrictions(restrictions, argument)


def record_comparison_restrictions(
    restrictions: list[DomainRestriction],
    operator: ast.cmpop,
    left: Expr | ImmutableMatrix,
    right: Expr | ImmutableMatrix,
) -> None:
    if isinstance(operator, ast.Eq | ast.NotEq):
        return
    if isinstance(left, ImmutableMatrix) or isinstance(right, ImmutableMatrix):
        return
    if left.is_extended_real is False or right.is_extended_real is False:
        raise MathDomainError("Invalid comparison: ordered comparisons require real values")
    _record_real_arguments(restrictions, (left, right))


def _record_real_arguments(
    restrictions: list[DomainRestriction], arguments: Sequence[SymbolicValue]
) -> None:
    for value in arguments:
        if not isinstance(value, Expr):
            continue
        if value.is_extended_real is False:
            raise MathDomainError("Ordered operations require real values")
        if value.free_symbols:
            record_restriction(
                restrictions, region_restriction(Ne(im(value, evaluate=False), Integer(0)))
            )
