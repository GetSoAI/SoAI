"""SoAI - Symbolic algebra, calculus and matrix operations [backend/core/math/symbolic_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

from sympy import (
    Add,
    Basic,
    Dummy,
    Eq,
    Expr,
    ImmutableMatrix,
    Integer,
    Integral,
    Mul,
    Not,
    Piecewise,
    Symbol,
    apart,
    cancel,
    expand,
    factor,
    false,
    integrate,
    nan,
    oo,
    product,
    series,
    simplify,
    summation,
    together,
    trigsimp,
    true,
    zoo,
)

from core.math.expression_limits import MAX_RESULT_DIGITS
from core.math.symbolic_bindings import substitute_symbols
from core.math.symbolic_branch_cuts import branch_cut_points
from core.math.symbolic_derivatives import differentiate
from core.math.symbolic_integral_checks import (
    checked_integral,
    has_unresolved_branch_parameters,
)
from core.math.symbolic_limits import evaluate_limit
from core.math.symbolic_matrices import build_symbolic_matrix_operations
from core.math.symbolic_operation_domains import bound_body_reachability
from core.math.symbolic_piecewise_forms import is_analytic, real_piecewise
from core.math.symbolic_precision import evaluate_symbolic_precision
from core.math.symbolic_solving import solve_equations
from core.math.symbolic_spans import integral_path
from core.math.symbolic_substitution import complete_integral, substitute_value
from core.math.symbolic_undefined import reports_undefined
from core.math.symbolic_values import (
    SYMBOLIC_FAILURES,
    require_bounded_integer,
    require_expression,
    require_single_value,
    require_symbol,
)

if TYPE_CHECKING:
    from core.math.symbolic_values import SymbolicValue

__all__ = ("build_symbolic_operations",)

_MAX_SERIES_ORDER = 50
_DEFAULT_SERIES_ORDER = 6
_DEFAULT_NUMERIC_DIGITS = 15
_MAX_LISTED_TERMS = 64


def build_symbolic_operations() -> dict[str, Callable[..., SymbolicValue]]:
    return {
        "simplify": _simplify,
        "expand": partial(_transform, function=expand),
        "factor": partial(_transform, function=factor),
        "cancel": partial(_transform, function=cancel),
        "together": partial(_transform, function=together),
        "trigsimp": partial(_transform, function=trigsimp),
        "apart": _partial_fractions,
        "solve": solve_equations,
        "subs": partial(substitute_value, evaluate_integral=_integrate),
        "N": _numeric_value,
        "diff": differentiate,
        "integrate": _integrate,
        "limit": evaluate_limit,
        "series": _series,
        "summation": partial(_indexed_operation, function=summation),
        "product": partial(_indexed_operation, function=product),
        **build_symbolic_matrix_operations(),
    }


def _simplify(value: SymbolicValue) -> Basic:
    return simplify(require_single_value(value, position=1))


def _transform(value: SymbolicValue, *, function: Callable[[Expr], Expr]) -> Expr:
    return function(require_expression(value, position=1))


def _partial_fractions(value: SymbolicValue, variable: SymbolicValue | None = None) -> Expr:
    expression = require_expression(value, position=1)
    if variable is None:
        return apart(expression)
    return apart(expression, require_symbol(variable, position=2))


def _numeric_value(
    value: SymbolicValue, digits: SymbolicValue | None = None
) -> Expr | ImmutableMatrix:
    precision = (
        _DEFAULT_NUMERIC_DIGITS
        if digits is None
        else require_bounded_integer(digits, position=2, maximum=MAX_RESULT_DIGITS)
    )
    if isinstance(value, Expr | ImmutableMatrix):
        return evaluate_symbolic_precision(value, precision)
    raise ValueError("argument 1 must be a number, an expression or a matrix")


def _integrate(
    value: SymbolicValue,
    variable: SymbolicValue,
    low: SymbolicValue | None = None,
    high: SymbolicValue | None = None,
) -> Expr:
    symbol = require_symbol(variable, position=2)
    integrand = require_expression(value, position=1)
    if (low is None) != (high is None):
        raise ValueError("provide both the low and high limits, or neither")
    limits = (
        symbol
        if low is None or high is None
        else (symbol, require_expression(low, position=3), require_expression(high, position=4))
    )
    empty = Eq(limits[1], limits[2]) if isinstance(limits, tuple) else false
    if empty == true:
        return Integer(0)
    if integrand.has(Integral):
        constant, varying = integrand.as_independent(symbol, as_Add=True)
        if constant.has(Integral):
            measure = _integrate(Integer(1), symbol, low, high)
            if measure.has(oo, -oo, zoo, nan):
                return Integral(integrand, limits)
            return constant * measure + _integrate(varying, symbol, low, high)
        constant, varying = integrand.as_independent(symbol, as_Add=False)
        if constant.has(Integral):
            evaluated = _integrate(varying, symbol, low, high)
            if evaluated.has(oo, -oo, zoo, nan, Integral):
                return Integral(integrand, limits)
            return constant * evaluated
    unknown_bounds = isinstance(limits, tuple) and any(
        bound.free_symbols and bound.is_finite is not True and bound.is_extended_real is not True
        for bound in limits[1:]
    )
    if (
        has_unresolved_branch_parameters(integrand, symbol)
        or integrand.has(Integral)
        or (unknown_bounds and not is_analytic(integrand, symbol))
    ):
        pending = Integral(integrand, limits)
        return Piecewise((Integer(0), empty), (complete_integral(pending, _integrate), true))
    path = integral_path(limits[1], limits[2]) if isinstance(limits, tuple) else None
    if path is not None:
        offset, scale, first, last = path
        parameter = Dummy("interval", real=True)
        integrand = scale * require_expression(
            substitute_symbols(integrand, {symbol: offset + scale * parameter}), position=1
        )
        symbol = parameter
        limits = (symbol, first, last)
    prepared = real_piecewise(integrand, symbol)
    if isinstance(limits, tuple):
        crossings = branch_cut_points(integrand, symbol)
        if crossings:
            checked = checked_integral(
                Integral(integrand, limits), integrand, *limits, branch_points=crossings
            )
            return Piecewise((Integer(0), empty), (checked, true))
    try:
        result = integrate(prepared, limits)
    except SYMBOLIC_FAILURES:
        if prepared == integrand:
            raise
        prepared = integrand
        result = integrate(prepared, limits)
    if result.has(Integral) and prepared != integrand:
        result = integrate(integrand, limits)
    if isinstance(limits, tuple):
        return Piecewise((Integer(0), empty), (checked_integral(result, integrand, *limits), true))
    return result


def _series(
    value: SymbolicValue,
    variable: SymbolicValue,
    point: SymbolicValue | None = None,
    order: SymbolicValue | None = None,
) -> Expr:
    expansion_point = Integer(0) if point is None else require_expression(point, position=3)
    expansion_order = (
        _DEFAULT_SERIES_ORDER
        if order is None
        else require_bounded_integer(order, position=4, maximum=_MAX_SERIES_ORDER)
    )
    return series(
        require_expression(value, position=1),
        require_symbol(variable, position=2),
        expansion_point,
        expansion_order,
    )


def _indexed_operation(
    value: SymbolicValue,
    index: SymbolicValue,
    low: SymbolicValue,
    high: SymbolicValue,
    *,
    function: Callable[[Expr, tuple[Symbol, Expr, Expr]], Expr],
) -> Expr:
    symbol = require_symbol(index, position=2)
    first = require_expression(low, position=3)
    last = require_expression(high, position=4)
    term = require_expression(value, position=1)
    if (
        isinstance(first, Integer)
        and isinstance(last, Integer)
        and -1 <= int(last) - int(first) < _MAX_LISTED_TERMS
    ):
        terms = [
            require_expression(term.subs(symbol, Integer(item)), position=1)
            for item in range(int(first), int(last) + 1)
        ]
        return Add(*terms) if function is summation else Mul(*terms)
    result = function(term, (symbol, first, last))
    if reports_undefined(term):
        name, identity = (
            ("summation", Integer(0)) if function is summation else ("product", Integer(1))
        )
        reached = bound_body_reachability(name, (term, symbol, first, last))
        return Piecewise((identity, Not(reached)), (result, true))
    return result
