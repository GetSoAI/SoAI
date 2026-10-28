"""SoAI - Whether conditions hold on the side of a point that a limit approaches [backend/core/math/symbolic_regions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import (
    Basic,
    Dummy,
    Eq,
    Expr,
    Gt,
    Integer,
    Lt,
    Piecewise,
    Poly,
    Rational,
    Rel,
    Symbol,
    ceiling,
    cos,
    diff,
    expand,
    false,
    floor,
    fraction,
    limit,
    piecewise_fold,
    sign,
    sin,
    tan,
    together,
    true,
)
from sympy.logic.boolalg import And, Boolean, Not, Or, simplify_logic

from core.math.symbolic_piecewise_forms import (
    floor_form,
    is_analytic,
    jump_functions,
    real_piecewise,
)
from core.math.symbolic_values import SYMBOLIC_FAILURES
from core.math.symbolic_vanishing import (
    UNDECIDED_CONDITION_MESSAGE,
    exponential_order,
    expression_of,
    identically_zero,
    leading_signs,
    vanishing_cases,
    vanishing_coefficients,
    zero_factors,
)

if TYPE_CHECKING:
    type Signs = tuple[Boolean, Boolean, Boolean]

__all__ = (
    "connect_condition",
    "near_condition",
    "settle_jumps",
    "simplest_condition",
)

_MAX_DEGREE = 8
_NEAR_DENOMINATORS = (1000, 7)
_FAR_POINTS = (1000, 1_000_000)
_MAX_SIMPLIFIED_RELATIONS = 6


def near_condition(condition: Boolean, symbol: Symbol, target: Expr, side: str) -> Boolean:
    if symbol not in condition.free_symbols:
        return condition
    if isinstance(condition, And | Or | Not):
        return connect_condition(
            condition,
            [
                near_condition(argument, symbol, target, side)
                for argument in condition.args
                if isinstance(argument, Boolean)
            ],
        )
    if not isinstance(condition, Rel):
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    difference = condition.lhs - condition.rhs
    if condition.rel_op in ("==", "!="):
        vanishes = _near_zero(difference, symbol, target, side)
        return vanishes if condition.rel_op == "==" else Not(vanishes)
    positive, negative, zero = _near_signs(difference, symbol, target, side)
    ordering = {
        ">": positive,
        ">=": Or(positive, zero),
        "<": negative,
        "<=": Or(negative, zero),
    }
    return ordering[condition.rel_op]


def settle_jumps(expression: Expr, symbol: Symbol, target: Expr, side: str) -> Expr:
    if target.free_symbols:
        return expression
    current = floor_form(expression, symbol)
    while True:
        settled: dict[Basic, Basic] = {}
        for jump in jump_functions(current, symbol):
            value = _settled(jump, symbol, target, side)
            if value is not None:
                settled[jump] = value
        if not settled:
            return current
        current = expression_of(current.xreplace(settled))


def simplest_condition(condition: Boolean) -> Boolean:
    if len(condition.atoms(Rel)) > _MAX_SIMPLIFIED_RELATIONS:
        return condition
    try:
        simplified = simplify_logic(condition)
    except SYMBOLIC_FAILURES:
        return condition
    return simplified if isinstance(simplified, Boolean) else condition


def connect_condition(connective: Boolean, parts: list[Boolean]) -> Boolean:
    if isinstance(connective, And):
        return And(*parts)
    if isinstance(connective, Or):
        return Or(*parts)
    return Not(parts[0])


def _near_signs(difference: Expr, symbol: Symbol, target: Expr, side: str) -> Signs:
    shaped = piecewise_fold(
        settle_jumps(piecewise_fold(real_piecewise(difference, symbol)), symbol, target, side)
    )
    if isinstance(shaped, Piecewise):
        signs: Signs = (false, false, false)
        remaining: Boolean = true
        for pair in shaped.args:
            reached = near_condition(pair.cond, symbol, target, side)
            branch = _near_signs(pair.expr, symbol, target, side)
            chosen = And(remaining, reached)
            signs = (
                Or(signs[0], And(chosen, branch[0])),
                Or(signs[1], And(chosen, branch[1])),
                Or(signs[2], And(chosen, branch[2])),
            )
            remaining = And(remaining, Not(reached))
        return signs
    shaped = expression_of(
        shaped.xreplace(
            {
                item: sin(expression_of(item.args[0])) / cos(expression_of(item.args[0]))
                for item in shaped.atoms(tan)
            }
        )
    )
    numerator, denominator = fraction(together(shaped))
    if numerator.is_polynomial(symbol) and denominator.is_polynomial(symbol):
        top = _polynomial_signs(numerator, symbol, target, side)
        bottom = _polynomial_signs(denominator, symbol, target, side)
    elif (shaped.free_symbols | target.free_symbols) - {symbol} and not target.is_infinite:
        top = _analytic_signs(numerator, symbol, target, side)
        bottom = _analytic_signs(denominator, symbol, target, side)
    else:
        value = _sign_limit(shaped, symbol, target, side)
        return (_truth(value == 1), _truth(value == -1), _truth(value == 0))
    return (
        Or(And(top[0], bottom[0]), And(top[1], bottom[1])),
        Or(And(top[0], bottom[1]), And(top[1], bottom[0])),
        top[2],
    )


def _polynomial_signs(polynomial: Expr, symbol: Symbol, target: Expr, side: str) -> Signs:
    try:
        if target.is_infinite:
            oriented = (
                polynomial.subs(symbol, -symbol) if target.is_extended_negative else polynomial
            )
            coefficients = Poly(expression_of(oriented), symbol).all_coeffs()
        else:
            step = Dummy("step")
            shifted = polynomial.subs(symbol, target + (step if side == "+" else -step))
            coefficients = Poly(expand(expression_of(shifted)), step).all_coeffs()[::-1]
        if len(coefficients) > _MAX_DEGREE + 1:
            raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    except SYMBOLIC_FAILURES as exception:
        raise ValueError(UNDECIDED_CONDITION_MESSAGE) from exception
    return leading_signs(coefficients)


def _analytic_signs(value: Expr, symbol: Symbol, target: Expr, side: str) -> Signs:
    order = exponential_order(value, symbol, _MAX_DEGREE + 1)
    if order is None:
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    coefficients: list[Expr] = []
    derivative = value
    for index in range(order):
        coefficient = expression_of(derivative.subs(symbol, target))
        coefficients.append(-coefficient if side == "-" and index % 2 else coefficient)
        derivative = diff(derivative, symbol)
    return leading_signs(coefficients)


def _near_zero(difference: Expr, symbol: Symbol, target: Expr, side: str) -> Boolean:
    numerator, _denominator = fraction(together(difference))
    factors = zero_factors(numerator)
    if factors != [numerator]:
        return Or(*(_near_zero(factor, symbol, target, side) for factor in factors))
    if symbol not in numerator.free_symbols:
        return Eq(numerator, Integer(0))
    if numerator.is_polynomial(symbol):
        return vanishing_coefficients(numerator, symbol)
    samples = _near_samples(target, side)
    if (numerator.free_symbols | target.free_symbols) - {symbol}:
        return vanishing_cases(
            numerator,
            samples,
            symbol,
            lambda values: _near_zero(
                expression_of(numerator.subs(values)),
                symbol,
                expression_of(target.subs(values)),
                side,
            )
            == true,
        )
    if is_analytic(numerator, symbol):
        return _truth(identically_zero(numerator, symbol, samples))
    return _near_signs(numerator, symbol, target, side)[2]


def _near_samples(target: Expr, side: str) -> list[Expr]:
    if target.is_infinite:
        return [Integer(point if target.is_extended_positive else -point) for point in _FAR_POINTS]
    return [
        target + Rational(1 if side == "+" else -1, denominator)
        for denominator in _NEAR_DENOMINATORS
    ]


def _settled(jump: Expr, symbol: Symbol, target: Expr, side: str) -> Expr | None:
    argument = jump.args[0]
    if (
        not isinstance(argument, Expr)
        or symbol not in argument.free_symbols
        or argument.has(Piecewise)
        or jump_functions(argument, symbol)
    ):
        return None
    try:
        start = limit(argument, symbol, target, side)
    except SYMBOLIC_FAILURES:
        return None
    if not (start.is_number and start.is_finite and start.is_extended_real):
        return None
    rounding = floor if isinstance(jump, floor) else ceiling
    if start.is_integer is not True:
        return rounding(start)
    above = near_condition(Gt(argument, start), symbol, target, side)
    below = near_condition(Lt(argument, start), symbol, target, side)
    if above == true:
        return start if rounding is floor else start + 1
    if below == true:
        return start - 1 if rounding is floor else start
    if above == false and below == false:
        return start
    return None


def _sign_limit(difference: Expr, symbol: Symbol, target: Expr, side: str) -> int:
    try:
        if any(
            not _approached(periodic.args[0], symbol, target, side).is_finite
            for periodic in difference.atoms(sin, cos, tan)
            if symbol in periodic.free_symbols
        ):
            raise ValueError(UNDECIDED_CONDITION_MESSAGE)
        value = _approached(sign(difference), symbol, target, side)
    except SYMBOLIC_FAILURES as exception:
        raise ValueError(UNDECIDED_CONDITION_MESSAGE) from exception
    if value not in (Integer(-1), Integer(0), Integer(1)):
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    if value == 0 and not identically_zero(difference, symbol, _near_samples(target, side)):
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    return 1 if value == Integer(1) else -1 if value == Integer(-1) else 0


def _approached(value: Basic, symbol: Symbol, target: Expr, side: str) -> Expr:
    if not isinstance(value, Expr):
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    return (
        limit(value, symbol, target) if target.is_infinite else limit(value, symbol, target, side)
    )


def _truth(value: bool) -> Boolean:
    return true if value else false
