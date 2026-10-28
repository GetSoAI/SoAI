"""SoAI - Derivatives that stay undefined where branches meet without a slope [backend/core/math/symbolic_derivatives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import (
    DiracDelta,
    Dummy,
    Eq,
    Expr,
    Gt,
    Heaviside,
    Integer,
    Limit,
    Lt,
    Mod,
    Piecewise,
    ceiling,
    cos,
    default_sort_key,
    diff,
    floor,
    nan,
    oo,
    piecewise_fold,
    sin,
    tan,
    together,
    true,
    zoo,
)
from sympy.logic.boolalg import And, Boolean, Not, Or

from core.math.symbolic_branch_cuts import branch_cut_points
from core.math.symbolic_domain import region_condition, region_restriction
from core.math.symbolic_limits import limit_of
from core.math.symbolic_piecewise_forms import (
    boundary_points,
    jump_functions,
    real_piecewise,
    undefined_region,
)
from core.math.symbolic_regions import near_condition
from core.math.symbolic_undefined import condition_at
from core.math.symbolic_values import (
    SYMBOLIC_FAILURES,
    require_bounded_integer,
    require_expression,
    require_symbol,
)
from core.math.symbolic_vanishing import expression_of

if TYPE_CHECKING:
    from sympy import Basic, Symbol

    from core.math.symbolic_values import DomainRestriction, SymbolicValue

__all__ = ("closed_restriction", "differentiate")

_MAX_DERIVATIVE_ORDER = 100
_MAX_JUMPS = 4
_UNFOUND_SLOPE_MESSAGE = "the slope where the branches of the expression meet could not be computed; substitute values for the parameters or simplify the expression"


def closed_restriction(restriction: DomainRestriction, symbol: Symbol) -> DomainRestriction:
    if region_condition(restriction.zero) is None or symbol not in restriction.zero.free_symbols:
        return restriction
    invalid = undefined_region(restriction)
    point: Symbol = Dummy("point", real=True)
    at_point = condition_at(invalid, {symbol: point})
    if point not in at_point.free_symbols:
        return region_restriction(at_point)
    if invalid.free_symbols == {symbol} and not invalid.has(sin, cos, tan):
        try:
            return region_restriction(invalid.as_set().closure.as_relational(symbol))
        except SYMBOLIC_FAILURES as exception:
            raise ValueError(_UNFOUND_SLOPE_MESSAGE) from exception
    closed = Or(
        at_point,
        near_condition(invalid, symbol, point, "+"),
        near_condition(invalid, symbol, point, "-"),
    )
    return region_restriction(condition_at(closed, {point: symbol}))


def differentiate(
    value: SymbolicValue,
    variable: SymbolicValue,
    order: SymbolicValue | None = None,
) -> Expr:
    count = (
        1
        if order is None
        else require_bounded_integer(order, position=3, maximum=_MAX_DERIVATIVE_ORDER)
    )
    expression = require_expression(value, position=1)
    symbol = require_symbol(variable, position=2)
    real_symbol = Dummy(symbol.name, real=True)
    current = real_piecewise(
        require_expression(expression.subs(symbol, real_symbol), position=1), real_symbol
    )
    if (
        not _has_branches(current, real_symbol)
        and not jump_functions(current, real_symbol)
        and not branch_cut_points(current, real_symbol)
    ):
        current = _without_kinks(diff(current, real_symbol, count), real_symbol)
    else:
        for _step in range(count):
            current = _derivative(current, real_symbol)
    return require_expression(current.subs(real_symbol, symbol), position=1)


def _without_kinks(derivative: Expr, symbol: Symbol) -> Expr:
    kinks = [
        Eq(expression_of(kink.args[0]), Integer(0))
        for function_type in (Heaviside, DiracDelta)
        for kink in derivative.atoms(function_type)
        if symbol in kink.free_symbols
    ]
    if not kinks:
        return derivative
    return piecewise_fold(Piecewise((nan, Or(*kinks)), (derivative, true)))


def _derivative(expression: Expr, symbol: Symbol) -> Expr:
    derivative = _local_derivative(expression, symbol)
    corrections: list[tuple[Expr, Boolean]] = []
    points = set(boundary_points(expression, symbol)) | set(branch_cut_points(expression, symbol))
    for point in sorted(points, key=default_sort_key):
        exact = _point_derivative(expression, symbol, point)
        try:
            formula = derivative.subs(symbol, point)
        except SYMBOLIC_FAILURES:
            formula = None
        if exact != formula or exact == nan:
            corrections.append((exact, Eq(symbol, point)))
    return piecewise_fold(
        Piecewise(
            *corrections,
            (_jump_slope(expression, symbol), _jump_region(expression, symbol)),
            (derivative, true),
        )
    )


def _local_derivative(expression: Expr, symbol: Symbol) -> Expr:
    jumps = [
        jump for jump in jump_functions(expression, symbol) if isinstance(jump, floor | ceiling)
    ]
    frozen: dict[Basic, Basic] = {jump: Dummy("jump") for jump in jumps}
    return expression_of(
        diff(expression_of(expression.xreplace(frozen)), symbol).xreplace(
            {placeholder: jump for jump, placeholder in frozen.items()}
        )
    )


def _jump_slope(expression: Expr, symbol: Symbol) -> Expr:
    folded = piecewise_fold(expression)
    if isinstance(folded, Piecewise):
        return Piecewise(*((_jump_slope(pair.expr, symbol), pair.cond) for pair in folded.args))
    if not jump_functions(folded, symbol):
        return _local_derivative(folded, symbol)
    above = _adjacent_expression(folded, symbol, "+")
    below = _adjacent_expression(folded, symbol, "-")
    upper_slope = _local_derivative(above, symbol)
    lower_slope = _local_derivative(below, symbol)
    continuous = And(
        Eq(together(above - folded), Integer(0)), Eq(together(below - folded), Integer(0))
    )
    agreed = Eq(together(upper_slope - lower_slope), Integer(0))
    return piecewise_fold(Piecewise((upper_slope, And(continuous, agreed)), (nan, true)))


def _adjacent_expression(expression: Expr, symbol: Symbol, side: str) -> Expr:
    jumps = jump_functions(expression, symbol)
    if len(jumps) > _MAX_JUMPS:
        raise ValueError(_UNFOUND_SLOPE_MESSAGE)
    step = Dummy("step")
    replacements: dict[Basic, Basic] = {}
    for jump in jumps:
        argument = expression_of(jump.args[0])
        if not isinstance(jump, floor | ceiling) or jump_functions(argument, symbol):
            raise ValueError(_UNFOUND_SLOPE_MESSAGE)
        change = expression_of(argument.subs(symbol, symbol + step)) - argument
        crossed = near_condition(
            Lt(change, 0) if isinstance(jump, floor) else Gt(change, 0),
            step,
            Integer(0),
            side,
        )
        at_integer = Eq(argument, floor(argument))
        offset = -1 if isinstance(jump, floor) else 1
        replacements[jump] = Piecewise((jump + offset, And(at_integer, crossed)), (jump, true))
    return piecewise_fold(expression_of(expression.xreplace(replacements)))


def _jump_region(expression: Expr, symbol: Symbol) -> Boolean:
    folded = piecewise_fold(expression)
    if not isinstance(folded, Piecewise):
        return _crossings(jump_functions(folded, symbol))
    regions: list[Boolean] = []
    earlier: list[Boolean] = []
    for pair in folded.args:
        active = And(pair.cond, *(Not(condition) for condition in earlier))
        regions.append(And(active, _jump_region(pair.expr, symbol)))
        regions.append(_crossings(jump_functions(pair.cond, symbol)))
        earlier.append(pair.cond)
    return Or(*regions)


def _crossings(jumps: list[Expr]) -> Boolean:
    crossings: list[Boolean] = []
    for jump in jumps:
        first, *rest = jump.args
        if not isinstance(first, Expr):
            continue
        argument = first
        if isinstance(jump, Mod) and rest and isinstance(rest[0], Expr):
            argument = first / rest[0]
        crossings.append(Eq(argument, floor(argument)))
    return Or(*crossings)


def _point_derivative(expression: Expr, symbol: Symbol, point: Expr) -> Expr:
    step = Dummy("step")
    try:
        value = expression_of(expression.subs(symbol, point))
    except SYMBOLIC_FAILURES:
        return nan
    shifted = expression_of(expression.subs(symbol, point + step))
    slope = limit_of((shifted - value) / step, step, Integer(0), None)
    if not isinstance(slope, Expr):
        return nan
    if slope.has(Limit) or step in slope.free_symbols:
        raise ValueError(_UNFOUND_SLOPE_MESSAGE)
    return _finite(slope)


def _finite(slope: Expr) -> Expr:
    if isinstance(slope, Piecewise):
        return piecewise_fold(Piecewise(*((_finite(pair.expr), pair.cond) for pair in slope.args)))
    return nan if slope.has(oo, -oo, zoo) else slope


def _has_branches(expression: Expr, symbol: Symbol) -> bool:
    return any(
        symbol in pair.cond.free_symbols
        for piecewise in expression.atoms(Piecewise)
        for pair in piecewise.args
    )
