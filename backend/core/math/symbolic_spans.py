"""SoAI - Whether conditions hold on part of an interval of positive length [backend/core/math/symbolic_spans.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from sympy import (
    Abs,
    Add,
    ConditionSet,
    Dummy,
    Eq,
    Expr,
    Function,
    Ge,
    Gt,
    I,
    Integer,
    Integral,
    Interval,
    Ne,
    Piecewise,
    Rational,
    Rel,
    S,
    Symbol,
    fraction,
    integrate,
    nan,
    oo,
    sign,
    sympify,
    together,
    true,
    zoo,
)
from sympy.logic.boolalg import And, Boolean, Not, Or

from core.math.symbolic_piecewise_forms import is_analytic
from core.math.symbolic_regions import connect_condition
from core.math.symbolic_values import SYMBOLIC_FAILURES
from core.math.symbolic_vanishing import (
    UNDECIDED_CONDITION_MESSAGE,
    expression_of,
    identically_zero,
    vanishing_cases,
    vanishing_coefficients,
    zero_factors,
)

__all__ = (
    "infinite_axis",
    "integral_path",
    "solved_condition",
    "span_condition",
    "span_contains",
    "unbounded_path",
)

_SPAN_FRACTIONS = ((1, 7), (1, 2), (6, 7))
_MAX_SOLVED_RELATIONS = 4
_UNBOUNDED_DIRECTION_MESSAGE = "the unbounded interval needs a single horizontal or vertical direction; parameterize the path using real bounds"


def integral_path(low: Expr, high: Expr) -> tuple[Expr, Expr, Expr, Expr] | None:
    direction = high - low
    unbounded = unbounded_path(low, high)
    if unbounded is not None:
        offset, axis, first, last = unbounded
        if axis == Integer(1) and all(bound.is_extended_real is True for bound in (low, high)):
            return (
                (Integer(0), Integer(-1), -low, -high)
                if direction.is_extended_negative is True
                else None
            )
        if (last - first).is_extended_negative is True:
            axis, first, last = -axis, -first, -last
        return offset, axis, first, last
    if (
        all(bound.is_finite is True for bound in (low, high))
        and not all(bound.is_extended_real is True for bound in (low, high))
    ) or (direction.is_number and direction.is_finite and direction.is_extended_real is False):
        return low, direction, Integer(0), Integer(1)
    return None


def infinite_axis(low: Expr, high: Expr) -> Expr | None:
    axes: set[Expr] = set()
    for bound in (low, high):
        if not bound.has(oo, -oo, zoo, nan):
            continue
        real, imaginary = bound.as_real_imag()
        if real.has(oo, -oo) and not imaginary.has(oo, -oo, zoo, nan):
            axes.add(Integer(1))
        elif imaginary.has(oo, -oo) and not real.has(oo, -oo, zoo, nan):
            axes.add(I)
        else:
            raise ValueError(_UNBOUNDED_DIRECTION_MESSAGE)
    if not axes:
        return None
    if len(axes) != 1:
        raise ValueError(_UNBOUNDED_DIRECTION_MESSAGE)
    return axes.pop()


def unbounded_path(low: Expr, high: Expr) -> tuple[Expr, Expr, Expr, Expr] | None:
    axis = infinite_axis(low, high)
    if axis is None:
        return None
    coordinates: list[Expr] = []
    heights: list[Expr] = []
    anchors: list[Expr] = []
    for bound in (low, high):
        real, imaginary = bound.as_real_imag()
        longitudinal, transverse = (real, imaginary) if axis == Integer(1) else (imaginary, -real)
        if bound.has(oo, -oo, zoo, nan):
            terms = longitudinal.args if isinstance(longitudinal, Add) else (longitudinal,)
            infinite = [term for term in terms if term.has(oo, -oo)]
            if len(infinite) != 1 or infinite[0] not in (oo, -oo):
                raise ValueError(_UNBOUNDED_DIRECTION_MESSAGE)
            coordinates.append(expression_of(infinite[0]))
            heights.append(transverse)
        else:
            coordinates.append(Integer(0))
            anchors.append(bound)
    if anchors:
        origin = anchors[0]
    else:
        if together(heights[0] - heights[1]).is_zero is not True:
            raise ValueError(
                "the unbounded endpoints must lie on the same line; parameterize the path using real bounds"
            )
        origin = axis * I * heights[0]
    return origin, axis, coordinates[0], coordinates[1]


def span_contains(point: Expr, low: Expr, high: Expr, *, strict: bool = False) -> Boolean:
    path = unbounded_path(low, high)
    beyond = Gt if strict else Ge
    if path is not None:
        origin, axis, start, end = path
        position, transverse = ((point - origin) / axis).as_real_imag()
        return And(
            Ne(low, high),
            Eq(transverse, Integer(0)),
            Or(
                And(beyond(position - start, 0), beyond(end - position, 0)),
                And(beyond(position - end, 0), beyond(start - position, 0)),
            ),
        )
    start, start_imaginary = low.as_real_imag()
    end, end_imaginary = high.as_real_imag()
    position, imaginary = point.as_real_imag()
    horizontal, vertical = end - start, end_imaginary - start_imaginary
    offset, offset_imaginary = position - start, imaginary - start_imaginary
    along = offset * horizontal + offset_imaginary * vertical
    across = offset_imaginary * horizontal - offset * vertical
    length_squared = horizontal**2 + vertical**2
    return And(
        Ne(low, high),
        Eq(across, Integer(0)),
        beyond(along, Integer(0)),
        beyond(length_squared - along, Integer(0)),
    )


def span_condition(condition: Boolean, symbol: Symbol, low: Expr, high: Expr) -> Boolean:
    if symbol not in condition.free_symbols:
        return And(condition, Ne(low, high))
    if not (condition.free_symbols | low.free_symbols | high.free_symbols) - {symbol}:
        measure = _measure(condition, low, high)
        if measure is not None:
            return true if measure.is_extended_positive is True else S.false
    equivalent = _measure_equivalent(condition, symbol, low, high)
    try:
        mass = integrate(
            Piecewise((Integer(1), equivalent), (Integer(0), true)), (symbol, low, high)
        )
    except SYMBOLIC_FAILURES as exception:
        raise ValueError(UNDECIDED_CONDITION_MESSAGE) from exception
    if mass.has(Integral):
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    return solved_condition(Ne(mass, Integer(0)))


def solved_condition(condition: Boolean) -> Boolean:
    if len(condition.free_symbols) != 1:
        return condition
    (parameter,) = condition.free_symbols
    relations = condition.atoms(Rel)
    if len(relations) > _MAX_SOLVED_RELATIONS or any(
        not isinstance(function, Abs | sign) for function in condition.atoms(Function)
    ):
        return condition
    probe = Dummy(parameter.name, real=True)
    probed = condition.xreplace({parameter: probe})
    if not isinstance(probed, Boolean):
        return condition
    try:
        solved = probed.as_set()
        relation = solved.as_relational(probe)
    except SYMBOLIC_FAILURES:
        return condition
    if not isinstance(solved, ConditionSet):
        resolved = relation.xreplace({probe: parameter})
        return resolved if isinstance(resolved, Boolean) else condition
    return condition


def _measure_equivalent(condition: Boolean, symbol: Symbol, low: Expr, high: Expr) -> Boolean:
    if symbol not in condition.free_symbols:
        return condition
    if isinstance(condition, And | Or | Not):
        return connect_condition(
            condition,
            [
                _measure_equivalent(argument, symbol, low, high)
                for argument in condition.args
                if isinstance(argument, Boolean)
            ],
        )
    if not isinstance(condition, Rel):
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    if condition.rel_op in ("==", "!="):
        vanishes = _span_zero(condition.lhs - condition.rhs, symbol, low, high)
        return vanishes if condition.rel_op == "==" else Not(vanishes)
    return condition


def _span_zero(difference: Expr, symbol: Symbol, low: Expr, high: Expr) -> Boolean:
    numerator, _denominator = fraction(together(difference))
    factors = zero_factors(numerator)
    if factors != [numerator]:
        return Or(*(_span_zero(factor, symbol, low, high) for factor in factors))
    if numerator.is_polynomial(symbol):
        return vanishing_coefficients(numerator, symbol)
    if not is_analytic(numerator, symbol):
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    samples = [
        low + (high - low) * Rational(numerator, denominator)
        for numerator, denominator in _SPAN_FRACTIONS
    ]
    if not numerator.free_symbols - {symbol}:
        return true if identically_zero(numerator, symbol, samples) else S.false
    return vanishing_cases(
        numerator,
        samples,
        symbol,
        lambda values: identically_zero(expression_of(numerator.subs(values)), symbol, samples),
    )


def _measure(condition: Boolean, low: Expr, high: Expr) -> Expr | None:
    try:
        span = Interval(low, high) if (high - low).is_extended_nonnegative else Interval(high, low)
        measure = sympify(condition.as_set().intersect(span).measure)
    except SYMBOLIC_FAILURES:
        return None
    return measure if isinstance(measure, Expr) and measure.is_number else None
