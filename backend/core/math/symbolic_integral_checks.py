"""SoAI - Exact antiderivative checks across singularities [backend/core/math/symbolic_integral_checks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import (
    Abs,
    AccumBounds,
    Add,
    Dummy,
    Expr,
    Integer,
    Integral,
    Limit,
    Max,
    Min,
    Piecewise,
    Pow,
    acos,
    acosh,
    asin,
    asinh,
    atan,
    atanh,
    ceiling,
    default_sort_key,
    floor,
    integrate,
    log,
    nan,
    oo,
    sign,
    true,
    zoo,
)

from core.math.symbolic_limits import limit_of
from core.math.symbolic_piecewise_forms import is_real_valued, polynomial_roots, real_piecewise
from core.math.symbolic_spans import span_contains
from core.math.symbolic_values import SYMBOLIC_FAILURES, require_expression
from core.math.symbolic_vanishing import zero_factors

if TYPE_CHECKING:
    from sympy import Basic, Symbol

__all__ = ("checked_integral", "has_unresolved_branch_parameters", "integral_branches")

_MAX_SINGULAR_POINTS = 16
_UNCHECKED_MESSAGE = "the integral could not be checked across its singularities; split the interval at those points or substitute values for the parameters first"


def has_unresolved_branch_parameters(
    integrand: Expr, symbol: Symbol, *, parameters: set[Symbol] | None = None
) -> bool:
    if parameters is None:
        parameters = integrand.free_symbols - {symbol}
    if not parameters or symbol not in integrand.free_symbols:
        return False
    coordinate = Dummy(symbol.name)
    integrand = require_expression(integrand.subs(symbol, coordinate), position=1)
    return any(
        argument.free_symbols & parameters and not is_real_valued(argument, coordinate)
        for branch in integral_branches(integrand, coordinate)
        for argument in branch.args
        if isinstance(argument, Expr)
    )


def integral_branches(integrand: Expr, symbol: Symbol) -> list[Expr]:
    branches: list[Expr] = [
        *integrand.atoms(
            Abs, sign, Min, Max, floor, ceiling, log, asin, acos, atan, asinh, acosh, atanh
        ),
        *(
            power
            for power in integrand.atoms(Pow)
            if power.exp.is_number and power.exp.is_integer is False
        ),
    ]
    return [branch for branch in branches if symbol in branch.free_symbols]


def checked_integral(
    result: Expr,
    integrand: Expr,
    symbol: Symbol,
    low: Expr,
    high: Expr,
    *,
    branch_points: tuple[Expr, ...] = (),
) -> Expr:
    unresolved = result.has(Integral)
    try:
        points = sorted(
            set(_singular_points(integrand, symbol)) | set(branch_points), key=default_sort_key
        )
        if not points or (
            unresolved and not branch_points and not integrand.is_rational_function(symbol)
        ):
            return _real_divergence(result, integrand, symbol, low, high)
        primitive = integrate(real_piecewise(integrand, symbol), symbol)
        if primitive.has(Integral):
            raise ValueError(_UNCHECKED_MESSAGE)
        if (integrand.free_symbols | low.free_symbols | high.free_symbols) - {symbol}:
            return _parameter_integral(result, primitive, integrand, symbol, low, high, points)
        if not (low.is_extended_real and high.is_extended_real):
            return result
        ascending = (high - low).is_extended_positive
        if ascending is None:
            raise ValueError(_UNCHECKED_MESSAGE)
        start, end = (low, high) if ascending else (high, low)
        inside = [
            point
            for point in points
            if (point - start).is_extended_positive and (end - point).is_extended_positive
        ]
        inside.sort()
        bounds = [start, *inside, end]
        pieces: list[Expr] = []
        for first, last in zip(bounds, bounds[1:], strict=False):
            above = require_expression(limit_of(primitive, symbol, first, "+"), position=1)
            below = require_expression(limit_of(primitive, symbol, last, "-"), position=1)
            if above.has(zoo, nan) or below.has(zoo, nan):
                raise ValueError(_UNCHECKED_MESSAGE)
            pieces.append(below - above)
        corrected = Add(*pieces)
        return _real_divergence(
            corrected if ascending else -corrected, integrand, symbol, low, high
        )
    except SYMBOLIC_FAILURES:
        if not unresolved:
            raise
        return result


def _parameter_integral(
    result: Expr,
    primitive: Expr,
    integrand: Expr,
    symbol: Symbol,
    low: Expr,
    high: Expr,
    points: list[Expr],
) -> Expr:
    jumps: list[tuple[Expr, Expr]] = []
    for point in points:
        below = require_expression(limit_of(primitive, symbol, point, "-"), position=1)
        above = require_expression(limit_of(primitive, symbol, point, "+"), position=1)
        if symbol in below.free_symbols | above.free_symbols or any(
            side.has(Limit, AccumBounds) for side in (below, above)
        ):
            raise ValueError(_UNCHECKED_MESSAGE)
        if below != above and not any(side.has(oo, -oo, zoo, nan) for side in (below, above)):
            jumps.append((point, below - above))
    if not jumps and not result.has(Integral):
        return _real_divergence(result, integrand, symbol, low, high)
    ascending = (high - low).is_extended_positive
    if ascending is None:
        raise ValueError(_UNCHECKED_MESSAGE)
    start, end = (low, high) if ascending else (high, low)
    above = require_expression(limit_of(primitive, symbol, start, "+"), position=1)
    below = require_expression(limit_of(primitive, symbol, end, "-"), position=1)
    corrections = [
        Piecewise((jump, span_contains(point, start, end, strict=True)), (Integer(0), true))
        for point, jump in jumps
    ]
    corrected = below - above + Add(*corrections)
    return corrected if ascending else -corrected


def _singular_points(integrand: Expr, symbol: Symbol) -> list[Expr]:
    singular: list[Basic] = [power.base for power in integrand.atoms(Pow) if power.exp.is_negative]
    singular.extend(argument for item in integrand.atoms(log) for argument in item.args)
    points: set[Expr] = set()
    for part in singular:
        if not isinstance(part, Expr):
            continue
        for factor in zero_factors(part):
            if symbol not in factor.free_symbols or not factor.is_polynomial(symbol):
                continue
            roots = polynomial_roots(factor, symbol, real_only=False)
            if roots is None:
                raise ValueError(_UNCHECKED_MESSAGE)
            points.update(roots)
            if len(points) > _MAX_SINGULAR_POINTS:
                raise ValueError(_UNCHECKED_MESSAGE)
    return sorted(points, key=default_sort_key)


def _real_divergence(result: Expr, integrand: Expr, symbol: Symbol, low: Expr, high: Expr) -> Expr:
    if not all(is_real_valued(value, symbol) for value in (integrand, low, high)):
        return result
    real, imaginary = result.as_real_imag()
    return real if real in (oo, -oo) and imaginary.is_finite is True else result
