"""SoAI - Function calls that solve, bind or substitute through domain restrictions [backend/core/math/symbolic_restricted_calls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from functools import partial
from itertools import islice
from typing import TYPE_CHECKING

from sympy import (
    And,
    Basic,
    Eq,
    Expr,
    FiniteSet,
    Integer,
    Le,
    Lt,
    Or,
    Range,
    S,
    Symbol,
    false,
    floor,
    nan,
    true,
    zoo,
)
from sympy.logic.boolalg import Boolean

from core.math.symbolic_derivatives import closed_restriction
from core.math.symbolic_domain import (
    active_restrictions,
    describe_condition,
    extend_restrictions,
    keep_conditional_restrictions,
    region_restriction,
    restriction_points,
    substitute_restrictions,
    undefined_condition,
)
from core.math.symbolic_limits import approach_sides, limit_direction
from core.math.symbolic_operation_domains import (
    BOUNDED_BODY_FUNCTIONS,
    bound_body_reachability,
    record_calculus_restrictions,
)
from core.math.symbolic_piecewise_forms import undefined_region
from core.math.symbolic_poles import crossed_poles
from core.math.symbolic_regions import near_condition
from core.math.symbolic_simplification_domains import record_function_simplification
from core.math.symbolic_spans import solved_condition, span_condition
from core.math.symbolic_undefined import absorb_undefined
from core.math.symbolic_values import SYMBOLIC_FAILURES

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sympy import Set

    from core.math.symbolic_values import DomainRestriction, SymbolicValue

__all__ = ("call_with_restrictions",)

_BINDING_FUNCTIONS = frozenset({"limit", "product", "summation"})
_RANGE_FUNCTIONS = frozenset({"product", "summation"})
_MAX_ENUMERATED_INDICES = 64
_UNCHECKED_RANGE_MESSAGE = "some terms of the range could not be checked for undefined values; split it into smaller ranges or simplify the term"
_SOLVE_FUNCTION = "solve"
_LIMIT_FUNCTION = "limit"
_DERIVATIVE_FUNCTION = "diff"
_SUBSTITUTE_FUNCTION = "subs"


def call_with_restrictions(
    name: str,
    function: Callable[..., SymbolicValue],
    arguments: Sequence[SymbolicValue],
    restrictions: list[DomainRestriction],
    argument_domains: Sequence[Sequence[DomainRestriction]],
    introduced: Sequence[DomainRestriction],
) -> SymbolicValue:
    scoped = (
        name in (_SUBSTITUTE_FUNCTION, _DERIVATIVE_FUNCTION)
        or _bound_variable(name, arguments) is not None
    )
    operand: list[DomainRestriction] = list(argument_domains[0]) if scoped else []
    if not scoped:
        for domain in argument_domains:
            extend_restrictions(operand, domain)
        extend_restrictions(operand, introduced)
    kept = _kept_restrictions(name, arguments, operand)
    if scoped:
        for domain in argument_domains[1:]:
            extend_restrictions(kept, domain)
        extend_restrictions(kept, introduced)
    try:
        result = _call(name, function, arguments, operand, kept)
        record_function_simplification(kept, name, arguments, result)
        if name == _DERIVATIVE_FUNCTION:
            record_calculus_restrictions(kept, arguments, result)
        return result
    finally:
        extend_restrictions(restrictions, kept)


def _call(
    name: str,
    function: Callable[..., SymbolicValue],
    arguments: Sequence[SymbolicValue],
    collected: Sequence[DomainRestriction],
    kept: Sequence[DomainRestriction],
) -> SymbolicValue:
    if name == _SOLVE_FUNCTION:
        return function(
            *arguments,
            excluded=tuple(
                restriction for restriction in collected if restriction.nonfinite_bindings is None
            ),
        )
    substitution = _substitution(arguments) if name == _SUBSTITUTE_FUNCTION else None
    if substitution is None:
        constant = [restriction for restriction in kept if not restriction.zero.free_symbols]
        if undefined_condition(constant, {}) == true:
            return nan
        bound = _bound_variable(name, arguments)
        operands = (
            arguments[1:] if bound is not None and name in BOUNDED_BODY_FUNCTIONS else arguments
        )
        return absorb_undefined(operands, function(*arguments), bound=bound)
    target, point = substitution
    found: SymbolicValue | None = None
    try:
        found = function(*arguments)
    except TypeError:
        if undefined_condition(collected, point) == false:
            raise
    considered = collected
    if found in (nan, zoo):
        considered = active_restrictions(collected, [target])
        extend_restrictions(
            considered,
            [
                restriction
                for restriction in collected
                if restriction.nonfinite_bindings is not None
            ],
        )
    undefined = undefined_condition(
        considered,
        point,
        substitute_integral=partial(function, variable=arguments[1], replacement=arguments[2]),
    )
    if undefined == true:
        return nan
    if found is None:
        raise ValueError(
            f"the result is undefined when {describe_condition(undefined)}; substitute values for the parameters in that condition first"
        )
    return absorb_undefined([target], found, point)


def _substitution(
    arguments: Sequence[SymbolicValue],
) -> tuple[Basic, dict[Symbol, Expr]] | None:
    target, variable, replacement = arguments
    if isinstance(target, Basic) and isinstance(variable, Symbol) and isinstance(replacement, Expr):
        return target, {variable: replacement}
    return None


def _bound_variable(name: str, arguments: Sequence[SymbolicValue]) -> Symbol | None:
    variable = arguments[1] if len(arguments) > 1 else None
    binds = name in _BINDING_FUNCTIONS or (name == "integrate" and len(arguments) == 4)
    return variable if binds and isinstance(variable, Symbol) else None


def _kept_restrictions(
    name: str, arguments: Sequence[SymbolicValue], collected: Sequence[DomainRestriction]
) -> list[DomainRestriction]:
    if name == _SOLVE_FUNCTION:
        return []
    if name == _DERIVATIVE_FUNCTION and isinstance(arguments[1], Symbol):
        derivative_domains = list(collected)
        extend_restrictions(
            derivative_domains,
            [
                closed_restriction(restriction, arguments[1])
                for restriction in collected
                if restriction.nonfinite_bindings is None
            ],
        )
        return derivative_domains
    variable = arguments[1] if name == _SUBSTITUTE_FUNCTION else _bound_variable(name, arguments)
    if not isinstance(variable, Symbol):
        return list(collected)
    kept: list[DomainRestriction] = []
    for restriction in collected:
        dependent_symbols = restriction.zero.free_symbols | restriction.condition.free_symbols
        if name == _SUBSTITUTE_FUNCTION and restriction.nonfinite_bindings is not None:
            dependent_symbols |= restriction.substitution_symbols
        if variable not in dependent_symbols:
            reached: Boolean = true
            if name in BOUNDED_BODY_FUNCTIONS:
                reached = bound_body_reachability(name, arguments)
            if reached == true:
                kept.append(restriction)
            else:
                extend_restrictions(kept, [restriction], condition=reached)
            continue
        if name == _SUBSTITUTE_FUNCTION and isinstance(replacement := arguments[2], Expr):
            kept.extend(substitute_restrictions([restriction], {variable: replacement}))
            continue
        if restriction.nonfinite_bindings is not None:
            continue
        if name in _RANGE_FUNCTIONS:
            for index, reached in _range_indices(restriction, variable, arguments[2], arguments[3]):
                kept.extend(
                    replace(indexed, condition=And(indexed.condition, reached))
                    for indexed in substitute_restrictions([restriction], {variable: index})
                )
        elif (reached := _bound_region(name, restriction, variable, arguments)) != false:
            kept.append(region_restriction(solved_condition(reached)))
    return keep_conditional_restrictions(kept)


def _bound_region(
    name: str, restriction: DomainRestriction, variable: Symbol, arguments: Sequence[SymbolicValue]
) -> Boolean:
    undefined = undefined_region(restriction)
    if name == _LIMIT_FUNCTION and isinstance(target := arguments[2], Expr):
        direction = limit_direction(arguments[3] if len(arguments) > 3 else None)
        return Or(
            *(
                near_condition(undefined, variable, target, side)
                for side in approach_sides(target, direction)
            )
        )
    integrand, _variable, low, high = arguments
    if isinstance(integrand, Expr) and isinstance(low, Expr) and isinstance(high, Expr):
        return Or(
            span_condition(undefined, variable, low, high),
            crossed_poles(restriction, variable, integrand, low, high),
        )
    return false


def _range_indices(
    restriction: DomainRestriction, variable: Symbol, low: SymbolicValue, high: SymbolicValue
) -> list[tuple[Expr, Boolean]]:
    if not (isinstance(low, Expr) and isinstance(high, Expr)):
        return []
    reversed_range = (high - low).is_negative
    first, last = (high + 1, low - 1) if reversed_range else (low, high)
    if (
        reversed_range is not None
        and first.is_extended_real is True
        and last.is_extended_real is True
    ):
        reached = And(restriction.condition, Le(first, variable), Le(variable, last))
        if reached == false or _condition_points(reached, variable) == S.EmptySet:
            return []
    concrete = (
        (int(first), int(last))
        if isinstance(first, Integer) and isinstance(last, Integer)
        else None
    )
    if concrete is not None and concrete[1] - concrete[0] < _MAX_ENUMERATED_INDICES:
        return [(Integer(index), true) for index in range(concrete[0], concrete[1] + 1)]
    points = restriction_points(restriction, variable)
    if points == S.EmptySet and restriction.zero.free_symbols <= {variable}:
        return []
    if not isinstance(points, FiniteSet):
        if concrete is not None:
            return _real_range_indices(restriction, variable, Range(concrete[0], concrete[1] + 1))
        raise ValueError(_UNCHECKED_RANGE_MESSAGE)
    indices: list[tuple[Expr, Boolean]] = []
    for point in points.args:
        if point.is_real is False:
            continue
        offset = point - low
        try:
            within = (
                Or(And(Le(low, point), Le(point, high)), And(Lt(high, point), Lt(point, low)))
                if reversed_range is None
                else And(Le(first, point), Le(point, last))
            )
        except TypeError as exception:
            raise ValueError(_UNCHECKED_RANGE_MESSAGE) from exception
        indices.append((point, And(Eq(floor(offset), offset), within)))
    return indices


def _real_range_indices(
    restriction: DomainRestriction, variable: Symbol, indices: Range
) -> list[tuple[Expr, Boolean]]:
    reached_anywhere = variable not in restriction.zero.free_symbols
    points = (
        _condition_points(restriction.condition, variable)
        if reached_anywhere
        else restriction_points(restriction, variable, domain=S.Reals)
    )
    inside = points.intersect(indices) if points is not None else None
    found = inside.args if isinstance(inside, FiniteSet) else inside
    if inside == S.EmptySet:
        return []
    if isinstance(found, tuple | Range) and (
        reached_anywhere
        or (found.size if isinstance(found, Range) else len(found)) <= _MAX_ENUMERATED_INDICES
        or variable not in restriction.condition.free_symbols
    ):
        return [(index, true) for index in islice(found, _MAX_ENUMERATED_INDICES)]
    raise ValueError(_UNCHECKED_RANGE_MESSAGE)


def _condition_points(condition: Boolean, variable: Symbol) -> Set | None:
    if condition.free_symbols != {variable}:
        return None
    try:
        return condition.as_set()
    except SYMBOLIC_FAILURES:
        return None
