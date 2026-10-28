"""SoAI - Piecewise forms, jumps, branch boundaries and undefined regions of expressions [backend/core/math/symbolic_piecewise_forms.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import (
    Abs,
    Add,
    Dummy,
    Eq,
    Expr,
    FiniteSet,
    Ge,
    Gt,
    I,
    Integer,
    Le,
    Lt,
    Max,
    Min,
    Mod,
    Mul,
    Piecewise,
    Poly,
    Pow,
    Rational,
    Rel,
    S,
    Symbol,
    atan,
    binomial,
    ceiling,
    cos,
    cosh,
    default_sort_key,
    erf,
    erfc,
    exp,
    expand_func,
    floor,
    fraction,
    gamma,
    im,
    piecewise_fold,
    re,
    sign,
    sin,
    sinh,
    solve,
    sqrt,
    tan,
    tanh,
    together,
    true,
)
from sympy.logic.boolalg import And, Boolean

from core.math.symbolic_domain import region_condition
from core.math.symbolic_undefined import condition_at
from core.math.symbolic_values import SYMBOLIC_FAILURES, require_expression
from core.math.symbolic_vanishing import zero_set

if TYPE_CHECKING:
    from collections.abc import Callable

    from sympy import Basic

    from core.math.symbolic_values import DomainRestriction

__all__ = (
    "boundary_points",
    "floor_form",
    "is_analytic",
    "is_real_valued",
    "jump_functions",
    "polynomial_roots",
    "polynomial_combinatorics",
    "real_piecewise",
    "undefined_region",
)

_MAX_BOUNDARY_POINTS = 16
_MAX_NESTED_REMAINDERS = 8
_ROOT_DIGITS = 40
_MAX_PARAMETRIC_DEGREE = 2
_IMAGINARY_TOLERANCE = 1e-20
_ANALYTIC_TYPES = (Add, Mul, exp, sin, cos, tan, sinh, cosh, tanh, atan, erf, erfc, gamma)
_REAL_TYPES = (*_ANALYTIC_TYPES, Abs, sign, floor, ceiling, Min, Max, Mod)
_KINK_TYPES = (Abs, sign, Min, Max, Mod)
_UNFOUND_BOUNDARIES_MESSAGE = "the points where the conditions of the expression switch could not all be found; substitute values for the parameters or simplify the conditions"


def real_piecewise(expression: Expr, symbol: Symbol) -> Expr:
    expression = polynomial_combinatorics(expression)
    if is_analytic(expression, symbol):
        return expression
    point = Dummy(symbol.name, real=True)
    prepared = require_expression(expression.subs(symbol, point), position=1)
    value = _real_piecewise(prepared, point)
    return require_expression(value.subs(point, symbol), position=1)


def polynomial_combinatorics(expression: Expr) -> Expr:
    return require_expression(
        expression.xreplace({term: expand_func(term) for term in expression.atoms(binomial)}),
        position=1,
    )


def _real_piecewise(expression: Expr, symbol: Symbol) -> Expr:
    if symbol not in expression.free_symbols or not expression.args:
        return expression
    if isinstance(expression, Piecewise):
        return Piecewise(
            *((_real_piecewise(pair.expr, symbol), pair.cond) for pair in expression.args)
        )
    arguments = [
        _real_piecewise(argument, symbol) if isinstance(argument, Expr) else argument
        for argument in expression.args
    ]
    rebuilt = (
        expression
        if all(new is old for new, old in zip(arguments, expression.args, strict=True))
        else expression.func(*arguments)
    )
    if not isinstance(rebuilt, Expr):
        return expression
    if isinstance(rebuilt, _KINK_TYPES) and any(
        isinstance(argument, Piecewise) for argument in rebuilt.args
    ):
        lifted = piecewise_fold(rebuilt)
        if isinstance(lifted, Piecewise):
            return Piecewise(
                *((_piecewise_form(pair.expr, symbol), pair.cond) for pair in lifted.args)
            )
    return _piecewise_form(rebuilt, symbol)


def floor_form(expression: Expr, symbol: Symbol) -> Expr:
    current = expression
    for _depth in range(_MAX_NESTED_REMAINDERS):
        remainders = {
            remainder: _piecewise_form(remainder, symbol)
            for remainder in current.atoms(Mod)
            if symbol in remainder.free_symbols
        }
        replaced = current.xreplace(
            {key: value for key, value in remainders.items() if value != key}
        )
        if replaced == current or not isinstance(replaced, Expr):
            return current
        current = replaced
    return current


def jump_functions(expression: Basic, symbol: Symbol) -> list[Expr]:
    found: set[Expr] = {*expression.atoms(floor), *expression.atoms(ceiling)}
    found.update(expression.atoms(Mod))
    return sorted((atom for atom in found if symbol in atom.free_symbols), key=default_sort_key)


def boundary_points(expression: Basic, symbol: Symbol) -> list[Expr]:
    points: set[Expr] = set()
    for piecewise in expression.atoms(Piecewise):
        for pair in piecewise.args:
            for relation in pair.cond.atoms(Rel):
                if symbol in relation.free_symbols:
                    numerator, denominator = fraction(together(relation.lhs - relation.rhs))
                    points.update(_roots(numerator, symbol))
                    points.update(_roots(denominator, symbol))
    if len(points) > _MAX_BOUNDARY_POINTS:
        raise ValueError(_UNFOUND_BOUNDARIES_MESSAGE)
    return sorted(points, key=default_sort_key)


def undefined_region(restriction: DomainRestriction) -> Boolean:
    region = region_condition(restriction.zero)
    reached = Eq(restriction.zero, Integer(0)) if region is None else region
    return And(reached, restriction.condition)


def is_analytic(value: Expr, symbol: Symbol) -> bool:
    if symbol not in value.free_symbols or isinstance(value, Symbol):
        return True
    if isinstance(value, Pow):
        if value.exp.is_integer is not True and symbol in value.base.free_symbols:
            return False
    elif not isinstance(value, _ANALYTIC_TYPES):
        return False
    return all(
        is_analytic(argument, symbol) for argument in value.args if isinstance(argument, Expr)
    )


def polynomial_roots(
    polynomial: Expr, symbol: Symbol, *, real_only: bool = True
) -> list[Expr] | None:
    try:
        if Poly(polynomial, symbol).LC().free_symbols:
            return None
        found = solve(polynomial, symbol, dict=True)
    except SYMBOLIC_FAILURES:
        return None
    if isinstance(found, Boolean):
        return None
    return [
        solution[symbol]
        for solution in found
        if symbol in solution and (not real_only or _possibly_real_root(solution[symbol]))
    ]


def _possibly_real_root(root: Expr) -> bool:
    if root.is_real is not None or not root.is_number:
        return root.is_real is not False
    _real, imaginary = root.evalf(_ROOT_DIGITS).as_real_imag()
    return not (imaginary.is_number and abs(imaginary) > _IMAGINARY_TOLERANCE)


def _roots(part: Expr, symbol: Symbol) -> list[Expr]:
    if symbol not in part.free_symbols:
        return []
    parameters = part.free_symbols - {symbol}
    if part.is_polynomial(symbol):
        if parameters and Poly(part, symbol).degree() > _MAX_PARAMETRIC_DEGREE:
            raise ValueError(_UNFOUND_BOUNDARIES_MESSAGE)
        roots = polynomial_roots(part, symbol)
        if roots is None:
            raise ValueError(_UNFOUND_BOUNDARIES_MESSAGE)
        return roots
    if parameters:
        raise ValueError(_UNFOUND_BOUNDARIES_MESSAGE)
    try:
        found = zero_set(part, symbol, S.Reals)
    except SYMBOLIC_FAILURES as exception:
        raise ValueError(_UNFOUND_BOUNDARIES_MESSAGE) from exception
    if not isinstance(found, FiniteSet):
        raise ValueError(_UNFOUND_BOUNDARIES_MESSAGE)
    return list(found.args)


def _piecewise_form(expression: Expr, symbol: Symbol) -> Expr:
    if symbol not in expression.free_symbols:
        return expression
    if (
        isinstance(expression, Pow)
        and abs(expression.exp) == Rational(1, 2)
        and isinstance(expression.base, Pow)
        and expression.base.exp == Integer(2)
    ):
        return _square_root_form(expression.base.base, expression.exp)
    operands = [argument for argument in expression.args if isinstance(argument, Expr)]
    if (
        isinstance(expression, Mod)
        and len(operands) == 2
        and all(is_real_valued(operand, symbol) for operand in operands)
    ):
        dividend, divisor = operands
        return dividend - divisor * floor(dividend / divisor)
    real_operands = bool(operands) and all(is_real_valued(operand, symbol) for operand in operands)
    if not real_operands and isinstance(expression, Abs):
        return _magnitude_form(expression)
    if not real_operands:
        return expression
    if isinstance(expression, Abs):
        (value,) = operands
        return Piecewise((value, Ge(value, 0)), (-value, true))
    if isinstance(expression, sign):
        (value,) = operands
        return Piecewise(
            (Integer(1), Gt(value, 0)), (Integer(-1), Lt(value, 0)), (Integer(0), true)
        )
    if isinstance(expression, Min):
        return _extreme(operands, symbol, Le)
    if isinstance(expression, Max):
        return _extreme(operands, symbol, Ge)
    return expression


def _magnitude_form(expression: Abs) -> Expr:
    argument = require_expression(expression.args[0], position=1)
    real, imaginary = argument.as_real_imag()
    return sqrt(real**2 + imaginary**2)


def _square_root_form(value: Expr, exponent: Expr) -> Expr:
    real, imaginary = value.as_real_imag()
    root = Piecewise((value, Gt(real, 0)), (-value, Lt(real, 0)), (I * Abs(imaginary), true))
    return root if exponent.is_positive else piecewise_fold(1 / root)


def _extreme(operands: list[Expr], symbol: Symbol, beats: Callable[[Expr, Expr], Boolean]) -> Expr:
    *contenders, last = operands
    point: Symbol = Dummy("point", real=True)
    branches: list[tuple[Expr, Boolean]] = []
    for operand in contenders:
        reached = And(*(beats(operand, other) for other in operands if other is not operand))
        real_condition = condition_at(reached, {symbol: point})
        branches.append((operand, condition_at(real_condition, {point: symbol})))
    return Piecewise(*branches, (last, true))


def _real_expression(value: Expr, symbol: Symbol) -> Expr:
    if symbol.is_real is True or symbol not in value.free_symbols:
        return value
    return require_expression(value.subs(symbol, Dummy(symbol.name, real=True)), position=1)


def is_real_valued(value: Expr, symbol: Symbol) -> bool:
    value = _real_expression(value, symbol)
    if value.is_number or isinstance(value, Symbol):
        return value.is_extended_real is True
    if isinstance(value, Abs | re | im):
        return True
    if isinstance(value, Piecewise):
        return all(is_real_valued(pair.expr, symbol) for pair in value.args)
    if isinstance(value, Pow):
        return (
            is_real_valued(value.base, symbol)
            and is_real_valued(value.exp, symbol)
            and (value.exp.is_integer is True or value.base.is_nonnegative is True)
        )
    if not isinstance(value, _REAL_TYPES):
        return False
    return all(
        is_real_valued(argument, symbol) for argument in value.args if isinstance(argument, Expr)
    )
