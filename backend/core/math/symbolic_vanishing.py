"""SoAI - Parameter values and samples that make symbolic expressions vanish [backend/core/math/symbolic_vanishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import (
    Abs,
    Add,
    ConditionSet,
    Dummy,
    Eq,
    Expr,
    Gt,
    I,
    Integer,
    Lt,
    Mul,
    Poly,
    Pow,
    S,
    Symbol,
    cos,
    cosh,
    default_sort_key,
    diff,
    exp,
    false,
    fraction,
    sign,
    simplify,
    sin,
    sinh,
    solve,
    solveset,
    together,
    true,
)
from sympy.logic.boolalg import And, Boolean, Or

from core.math.symbolic_precision import evaluate_symbolic_precision
from core.math.symbolic_values import SYMBOLIC_FAILURES

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sympy import Basic, Set

__all__ = (
    "UNDECIDED_CONDITION_MESSAGE",
    "expression_of",
    "exponential_order",
    "identically_zero",
    "number_signs",
    "leading_signs",
    "parameter_zeros",
    "vanishing_cases",
    "vanishing_coefficients",
    "zero_factors",
    "zero_set",
)

UNDECIDED_CONDITION_MESSAGE = "the conditions in the expression could not be decided next to the point or across the interval; substitute values for the parameters or simplify the conditions"
_NONZERO_MAGNITUDE = 1e-20
_NUMERIC_DIGITS = 40
_MAX_PARAMETER_ZEROS = 4


def exponential_order(value: Expr, symbol: Symbol, maximum: int) -> int | None:
    if symbol not in value.free_symbols:
        return 1
    if isinstance(value, exp | sin | cos | sinh | cosh):
        argument = expression_of(value.args[0])
        return (
            (1 if isinstance(value, exp) else 2)
            if argument.is_polynomial(symbol) and diff(argument, symbol, 2) == 0
            else None
        )
    if isinstance(value, Pow) and isinstance(value.exp, Integer) and value.exp.is_nonnegative:
        order = exponential_order(value.base, symbol, maximum)
        if order is None or (order > 1 and value.exp > maximum):
            return None
        bound = (
            (order - 1) * int(value.exp) + 1
            if value.base.is_polynomial(symbol)
            else order ** int(value.exp)
        )
    elif isinstance(value, Add | Mul):
        bound = 0 if isinstance(value, Add) else 1
        polynomial_order = 0 if isinstance(value, Add) else 1
        combined = bound
        for part in value.args:
            expression = expression_of(part)
            order = exponential_order(expression, symbol, maximum)
            if order is None:
                return None
            if expression.is_polynomial(symbol):
                polynomial_order = (
                    max(polynomial_order, order)
                    if isinstance(value, Add)
                    else polynomial_order + order - 1
                )
            else:
                bound = bound + order if isinstance(value, Add) else bound * order
            combined = (
                bound + polynomial_order if isinstance(value, Add) else bound * polynomial_order
            )
            if combined > maximum:
                return None
        bound = combined
    elif value == symbol:
        bound = 2
    else:
        return None
    return bound if bound <= maximum else None


def leading_signs(coefficients: Sequence[Expr]) -> tuple[Boolean, Boolean, Boolean]:
    positive: list[Boolean] = []
    negative: list[Boolean] = []
    vanished: list[Boolean] = []
    for coefficient in coefficients:
        if coefficient.is_number:
            above, below, zero = number_signs(coefficient)
        else:
            real = coefficient.xreplace(
                {
                    parameter: Dummy(parameter.name, real=True)
                    for parameter in coefficient.free_symbols
                }
            )
            above, below, zero = Gt(coefficient, 0), Lt(coefficient, 0), Eq(coefficient, Integer(0))
            if isinstance(real, Expr):
                if real.is_positive is True:
                    above, below, zero = true, false, false
                elif real.is_negative is True:
                    above, below, zero = false, true, false
                elif real.is_zero is True:
                    above, below, zero = false, false, true
        positive.append(And(*vanished, above))
        negative.append(And(*vanished, below))
        vanished.append(zero)
    return Or(*positive), Or(*negative), And(*vanished)


def identically_zero(value: Expr, symbol: Symbol, samples: Sequence[Expr]) -> bool:
    for sample in samples:
        try:
            number = expression_of(value.subs(symbol, sample)).evalf(_NUMERIC_DIGITS)
        except SYMBOLIC_FAILURES:
            continue
        if number.is_number and number.is_finite and abs(number) > _NONZERO_MAGNITUDE:
            return False
    return simplify(value) == 0


def zero_set(value: Expr, symbol: Symbol, domain: Set = S.Complexes) -> Set:
    candidates = solveset(value, symbol, domain=domain)
    if isinstance(candidates, ConditionSet) or not (
        candidates in (S.Complexes, S.Reals) or candidates.has(S.Complexes, S.Reals)
    ):
        return candidates
    coordinate = Dummy(symbol.name, real=True) if candidates == S.Reals else symbol
    residual = expression_of(value.subs(symbol, coordinate))
    samples: tuple[Expr, ...] = (Integer(-1), Integer(0), Integer(1))
    if candidates != S.Reals:
        samples = (*samples, I, -I)
    if identically_zero(residual, coordinate, samples):
        return candidates
    return ConditionSet(symbol, Eq(value, Integer(0)), candidates)


def vanishing_cases(
    difference: Expr,
    samples: Sequence[Expr],
    symbol: Symbol,
    vanishes: Callable[[dict[Symbol, Expr]], bool],
) -> Boolean:
    sampled = [expression_of(difference.subs(symbol, sample)) for sample in samples]
    if any(not value.free_symbols and value.is_zero is not False for value in sampled):
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    cases: list[Boolean] = []
    for values in parameter_zeros(sampled):
        remaining = expression_of(difference.subs(values)).free_symbols - {symbol}
        if not remaining and vanishes(values):
            cases.append(And(*(Eq(name, value) for name, value in values.items())))
    return Or(*cases)


def parameter_zeros(conditions: Sequence[Expr]) -> list[dict[Symbol, Expr]]:
    found: list[dict[Symbol, Expr]] = []
    for condition in conditions:
        for values in _zeros(condition):
            if values not in found:
                found.append(values)
                if len(found) > _MAX_PARAMETER_ZEROS:
                    raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    return found


def _zeros(condition: Expr) -> list[dict[Symbol, Expr]]:
    if not condition.free_symbols:
        return []
    factors = zero_factors(condition)
    if factors != [condition]:
        return [values for factor in factors for values in _zeros(factor)]
    numerator, _denominator = fraction(together(condition))
    symbols = sorted(numerator.free_symbols, key=default_sort_key)
    if not symbols:
        return []
    if not numerator.is_polynomial(*symbols):
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    try:
        solutions = solve(numerator, *symbols, dict=True)
    except SYMBOLIC_FAILURES as exception:
        raise ValueError(UNDECIDED_CONDITION_MESSAGE) from exception
    return [] if isinstance(solutions, Boolean) else solutions


def zero_factors(value: Expr) -> list[Expr]:
    if isinstance(value, Mul):
        return [
            part
            for factor in value.args
            if isinstance(factor, Expr)
            for part in zero_factors(factor)
        ]
    if isinstance(value, Pow) and value.exp.is_positive is True:
        return zero_factors(value.base)
    if isinstance(value, Abs | sign) and isinstance(value.args[0], Expr):
        return zero_factors(value.args[0])
    return [value]


def vanishing_coefficients(polynomial: Expr, symbol: Symbol) -> Boolean:
    try:
        coefficients = Poly(polynomial, symbol).all_coeffs()
    except SYMBOLIC_FAILURES as exception:
        raise ValueError(UNDECIDED_CONDITION_MESSAGE) from exception
    return And(*(Eq(coefficient, Integer(0)) for coefficient in coefficients))


def expression_of(value: Basic) -> Expr:
    if isinstance(value, Expr):
        return value
    raise ValueError(UNDECIDED_CONDITION_MESSAGE)


def number_signs(number: Expr) -> tuple[Boolean, Boolean, Boolean]:
    real, imaginary = evaluate_symbolic_precision(number, _NUMERIC_DIGITS).as_real_imag()
    if not (real.is_number and imaginary.is_number) or imaginary.is_zero is not True:
        raise ValueError(UNDECIDED_CONDITION_MESSAGE)
    if real.is_zero is False:
        return (true if real > 0 else false, true if real < 0 else false, false)
    if simplify(number) == 0:
        return (false, false, true)
    raise ValueError(UNDECIDED_CONDITION_MESSAGE)
