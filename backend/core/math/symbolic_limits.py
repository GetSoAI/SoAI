"""SoAI - Limits that follow the approached branch and parameter special cases [backend/core/math/symbolic_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import (
    AccumBounds,
    Basic,
    Dummy,
    Eq,
    Expr,
    Integer,
    Limit,
    Max,
    Min,
    Piecewise,
    Poly,
    Pow,
    Rel,
    Symbol,
    cos,
    false,
    fraction,
    limit,
    nan,
    oo,
    piecewise_fold,
    sign,
    sin,
    sstr,
    tan,
    together,
    trigsimp,
    true,
    zoo,
)
from sympy.logic.boolalg import And, Boolean, Not, Or

from core.math.result_projection import OUTCOME_NO_LIMIT
from core.math.symbolic_piecewise_forms import jump_functions, real_piecewise
from core.math.symbolic_regions import near_condition, settle_jumps, simplest_condition
from core.math.symbolic_spans import solved_condition
from core.math.symbolic_undefined import undefined_when
from core.math.symbolic_values import (
    SYMBOLIC_FAILURES,
    SymbolicOutcome,
    require_expression,
    require_symbol,
)
from core.math.symbolic_vanishing import parameter_zeros, zero_factors

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.math.symbolic_values import SymbolicValue

__all__ = (
    "approach_sides",
    "evaluate_limit",
    "limit_direction",
    "limit_of",
)

_MAX_CASE_DEPTH = 3
_MAX_PAIRED_CASES = 16
_MAX_RESULT_RELATIONS = 24
_TOO_MANY_CASES_MESSAGE = "the result splits into too many cases for the parameters; substitute values for the parameters first"
_LIMIT_FAILURE_MESSAGE = (
    "this limit could not be computed; simplify the expression or take a one-sided limit"
)
_PARAMETRIC_JUMP_MESSAGE = "the limit of floor, ceil or % depends on whether the parameters make its argument a whole number at the point; substitute values for the parameters first"


def evaluate_limit(
    value: SymbolicValue,
    variable: SymbolicValue,
    point: SymbolicValue,
    side: SymbolicValue | None = None,
) -> SymbolicValue:
    symbol = require_symbol(variable, position=2)
    target = require_expression(point, position=3)
    expression = require_expression(value, position=1)
    if target.is_infinite is not True:
        coordinate = Dummy(symbol.name, real=True)
        expression = require_expression(expression.subs(symbol, target + coordinate), position=1)
        symbol, target = coordinate, Integer(0)
    if target.is_extended_real is True:
        expression = real_piecewise(expression, symbol)
    if expression.has(sin, cos, tan):
        expression = trigsimp(expression)
    return limit_of(expression, symbol, target, limit_direction(side))


def limit_direction(side: SymbolicValue | None) -> str | None:
    if side is None:
        return None
    if side == Integer(1):
        return "+"
    if side == Integer(-1):
        return "-"
    raise ValueError("argument 4 must be 1 (approach from above) or -1 (approach from below)")


def approach_sides(target: Expr, direction: str | None) -> tuple[str, ...]:
    if target.is_infinite:
        return ("+" if target.is_extended_negative else "-",)
    return ("+", "-") if direction is None else (direction,)


def limit_of(
    expression: Expr, symbol: Symbol, target: Expr, direction: str | None
) -> SymbolicValue:
    values = [
        _bounded(_sided(expression, symbol, target, side, depth=0))
        for side in approach_sides(target, direction)
    ]
    if len(values) == 1:
        return values[0]
    above, below = values
    if above.has(Limit) or below.has(Limit):
        return above if above == below else Limit(expression, symbol, target, "+-")
    return _bounded(_two_sided(above, below))


def _bounded[Value: SymbolicValue](value: Value) -> Value:
    if isinstance(value, Basic) and len(value.atoms(Rel)) > _MAX_RESULT_RELATIONS:
        raise ValueError(_TOO_MANY_CASES_MESSAGE)
    return value


def _sided(expression: Expr, symbol: Symbol, target: Expr, side: str, *, depth: int) -> Expr:
    folded = piecewise_fold(settle_jumps(piecewise_fold(expression), symbol, target, side))
    if isinstance(folded, Piecewise):
        return _branch_limit(folded, symbol, target, side, depth=depth)
    for jump in jump_functions(folded, symbol):
        if _unsettled(jump, symbol, target):
            raise ValueError(
                _PARAMETRIC_JUMP_MESSAGE
                if (jump.free_symbols | target.free_symbols) - {symbol}
                else _LIMIT_FAILURE_MESSAGE
            )
    try:
        generic = (
            limit(folded, symbol, target)
            if target.is_infinite
            else limit(folded, symbol, target, side)
        )
    except SYMBOLIC_FAILURES as exception:
        raise ValueError(_LIMIT_FAILURE_MESSAGE) from exception
    if generic.has(AccumBounds) and not isinstance(generic, AccumBounds):
        scale, bounds = generic.as_independent(AccumBounds, as_Add=False)
        if not (
            isinstance(bounds, AccumBounds)
            and scale.is_extended_real is True
            and scale.is_finite is True
        ):
            raise ValueError(_LIMIT_FAILURE_MESSAGE)
        first, last = scale * bounds.min, scale * bounds.max
        generic = AccumBounds(Min(first, last), Max(first, last))
    if generic.has(Limit):
        return generic
    singular: list[Basic] = [fraction(together(generic))[1]]
    singular.extend(item.args[0] for item in generic.atoms(sign))
    singular.extend(item.base for item in generic.atoms(Pow) if item.exp.is_negative)
    if target.is_infinite:
        singular.extend(
            Poly(polynomial, symbol).LC()
            for polynomial in fraction(together(folded))
            if polynomial.is_polynomial(symbol)
        )
    else:
        singular.append(fraction(together(folded))[1].subs(symbol, target))
    conditions = list(
        dict.fromkeys(
            factor
            for item in singular
            if isinstance(item, Expr)
            for factor in zero_factors(item)
            if factor.free_symbols and symbol not in factor.free_symbols
        )
    )
    cases: list[tuple[Expr, Boolean]] = []
    for condition in conditions:
        substitutions: list[tuple[Mapping[Basic, Basic], Boolean]] = [
            ({condition: Integer(0)}, Eq(condition, Integer(0)))
        ]
        if folded.subs(condition, Integer(0)) == folded:
            substitutions = [
                (
                    dict[Basic, Basic](values.items()),
                    And(*(Eq(name, value) for name, value in values.items())),
                )
                for values in parameter_zeros([condition])
            ]
        for values, reached in substitutions:
            if depth >= _MAX_CASE_DEPTH:
                raise ValueError(_TOO_MANY_CASES_MESSAGE)
            special = _special_limit(folded, symbol, target, side, values, depth=depth)
            if special != generic.subs(values):
                cases.append((special, reached))
        if len(cases) > _MAX_PAIRED_CASES:
            raise ValueError(_TOO_MANY_CASES_MESSAGE)
    return piecewise_fold(Piecewise(*cases, (generic, true))) if cases else generic


def _special_limit(
    folded: Expr,
    symbol: Symbol,
    target: Expr,
    side: str,
    values: Mapping[Basic, Basic],
    *,
    depth: int,
) -> Expr:
    substituted = require_expression(folded.subs(values), position=1)
    return (
        nan
        if substituted.has(zoo, nan)
        else _sided(
            substituted,
            symbol,
            require_expression(target.subs(values), position=3),
            side,
            depth=depth + 1,
        )
    )


def _unsettled(jump: Expr, symbol: Symbol, target: Expr) -> bool:
    if not target.is_infinite:
        return bool((jump.free_symbols | target.free_symbols) - {symbol})
    argument = jump.args[0]
    try:
        approached = limit(argument, symbol, target) if isinstance(argument, Expr) else nan
    except SYMBOLIC_FAILURES:
        return True
    return not (approached.is_infinite or isinstance(approached, AccumBounds))


def _branch_limit(
    folded: Piecewise, symbol: Symbol, target: Expr, side: str, *, depth: int
) -> Expr:
    branches: list[tuple[Expr, Boolean]] = []
    for pair in folded.args:
        reached = near_condition(pair.cond, symbol, target, side)
        if reached == false:
            continue
        branches.append((_sided(pair.expr, symbol, target, side, depth=depth), reached))
        if reached == true:
            break
    else:
        branches.append((nan, true))
    return _tidy(piecewise_fold(Piecewise(*branches)))


def _two_sided(above: Expr, below: Expr) -> SymbolicValue:
    if above == below:
        return above
    if isinstance(above, Piecewise) or isinstance(below, Piecewise):
        upper_cases = _exclusive_branches(above)
        lower_cases = _exclusive_branches(below)
        if len(upper_cases) * len(lower_cases) > _MAX_PAIRED_CASES:
            raise ValueError(_TOO_MANY_CASES_MESSAGE)
        cases: list[tuple[Expr, Boolean]] = [
            (_agreement(upper, lower), And(reached, met))
            for upper, reached in upper_cases
            for lower, met in lower_cases
        ]
        return _tidy(
            piecewise_fold(Piecewise(*((value, case) for value, case in cases if case != false)))
        )
    agreed = _agreement(above, below)
    if agreed == nan:
        return SymbolicOutcome(
            outcome=OUTCOME_NO_LIMIT,
            text="does not exist",
            note=f"the two-sided limit does not exist: from below it is {sstr(below)}, from above it is {sstr(above)}",
        )
    return agreed


def _exclusive_branches(value: Expr) -> list[tuple[Expr, Boolean]]:
    if not isinstance(value, Piecewise):
        return [(value, true)]
    branches: list[tuple[Expr, Boolean]] = []
    earlier: list[Boolean] = []
    for pair in value.args:
        branches.append((pair.expr, And(pair.cond, *(Not(item) for item in earlier))))
        earlier.append(pair.cond)
    return branches


def _agreement(above: Expr, below: Expr) -> Expr:
    if above == below:
        return above
    if any(side.has(oo, -oo, zoo, nan) for side in (above, below)):
        return nan
    agreed = Eq(fraction(together(above - below))[0], Integer(0))
    return nan if agreed == false else undefined_when(above, Not(agreed))


def _tidy(expression: Expr) -> Expr:
    if not isinstance(expression, Piecewise):
        return expression
    branches: list[tuple[Expr, Boolean]] = []
    earlier: list[Boolean] = []
    for pair in expression.args:
        exclusive = And(pair.cond, *(Not(item) for item in earlier))
        earlier.append(pair.cond)
        reached = (
            solved_condition(exclusive)
            if len(exclusive.free_symbols) == 1
            else simplest_condition(exclusive)
        )
        if reached == false:
            continue
        if pair.cond == true:
            reached = true
        if branches and branches[-1][0] == pair.expr:
            branches[-1] = (pair.expr, Or(branches[-1][1], reached))
        else:
            branches.append((pair.expr, reached))
        if reached == true:
            break
    return Piecewise(*branches) if branches else nan
