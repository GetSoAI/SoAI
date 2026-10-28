"""SoAI - Domain restrictions recorded before sympy simplifies them away [backend/core/math/symbolic_domain.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from sympy import (
    AccumBounds,
    And,
    Basic,
    Contains,
    Dummy,
    Expr,
    FiniteSet,
    ImageSet,
    Integer,
    Integral,
    Lambda,
    Ne,
    Not,
    Or,
    Piecewise,
    Pow,
    Rel,
    S,
    Symbol,
    Union,
    factorial,
    false,
    gamma,
    sstr,
    true,
    zoo,
)
from sympy.logic.boolalg import Boolean

from core.math.symbolic_bindings import (
    compose_symbol_substitutions,
    substitute_operation_operands,
    substitute_symbols,
)
from core.math.symbolic_undefined import condition_at, undefined_branches
from core.math.symbolic_values import SYMBOLIC_FAILURES, DomainRestriction
from core.math.symbolic_vanishing import zero_set

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from sympy import Set

    from core.math.symbolic_values import Substitution, SymbolicValue

__all__ = (
    "active_restrictions",
    "applies_at",
    "describe_condition",
    "extend_restrictions",
    "is_excluded",
    "keep_conditional_restrictions",
    "localize_restrictions",
    "record_restriction",
    "region_condition",
    "region_restriction",
    "required_condition",
    "restriction_points",
    "substitute_restrictions",
    "undefined_condition",
)


def describe_condition(condition: Boolean) -> str:
    if isinstance(condition, Rel):
        return f"{sstr(condition.lhs)} {condition.rel_op} {sstr(condition.rhs)}"
    return sstr(condition)


def extend_restrictions(
    restrictions: list[DomainRestriction],
    additions: Sequence[DomainRestriction],
    *,
    condition: Boolean = true,
) -> None:
    if condition == false:
        return
    for addition in additions:
        if addition in restrictions or (
            addition.condition != true and replace(addition, condition=true) in restrictions
        ):
            continue
        guarded = (
            addition
            if condition == true
            else replace(addition, condition=And(addition.condition, condition))
        )
        record_restriction(restrictions, guarded)


def substitute_restrictions(
    restrictions: Sequence[DomainRestriction], values: Substitution
) -> list[DomainRestriction]:
    substituted: list[DomainRestriction] = []
    for restriction in restrictions:
        if (region := region_condition(restriction.zero)) is not None:
            substituted.append(
                replace(
                    region_restriction(condition_at(region, values)),
                    condition=condition_at(restriction.condition, values),
                )
            )
            continue
        bindings = restriction.nonfinite_bindings
        if bindings is not None:
            bindings = compose_symbol_substitutions(restriction.term.free_symbols, bindings, values)
            term: Basic = restriction.term
        else:
            term = substitute_symbols(restriction.term, values)
        zero = substitute_symbols(restriction.zero, values)
        condition = condition_at(restriction.condition, values)
        if isinstance(term, Expr) and isinstance(zero, Expr):
            substituted.append(
                replace(
                    restriction,
                    term=term,
                    zero=zero,
                    condition=condition,
                    nonfinite_bindings=bindings,
                )
            )
    return substituted


def keep_conditional_restrictions(
    restrictions: Sequence[DomainRestriction],
) -> list[DomainRestriction]:
    kept: list[DomainRestriction] = []
    for restriction in restrictions:
        if restriction.zero.free_symbols or not restriction.condition.free_symbols:
            kept.append(restriction)
            continue
        if restriction.nonfinite_bindings is not None:
            kept.append(
                restriction
                if restriction.substitution_symbols
                else region_restriction(undefined_condition([restriction], {}))
            )
        elif undefined_branches(restriction.zero, vanishing=True) == true:
            kept.append(region_restriction(restriction.condition))
        else:
            kept.append(restriction)
    return kept


def localize_restrictions(
    restrictions: Sequence[DomainRestriction], unknowns: Sequence[Symbol]
) -> list[DomainRestriction]:
    localized: list[DomainRestriction] = []
    unknown_set = set(unknowns)
    for restriction in restrictions:
        extend_restrictions(localized, _localize(restriction, unknown_set))
    return localized


def restriction_points(
    restriction: DomainRestriction, symbol: Symbol, *, domain: Set = S.Complexes
) -> Set | None:
    zero = restriction.zero
    try:
        if isinstance(zero, gamma | factorial):
            return S.EmptySet
        if isinstance(zero, Pow) and zero.exp == Integer(-1) and isinstance(zero.base, gamma):
            return _gamma_poles(zero.base.args[0], symbol, domain)
        return zero_set(zero, symbol, domain=domain)
    except SYMBOLIC_FAILURES:
        return None


def region_condition(zero: Expr) -> Boolean | None:
    if not isinstance(zero, Piecewise) or len(zero.args) != 2:
        return None
    inside, outside = zero.args
    if inside.expr == Integer(0) and outside.cond == true and outside.expr.is_zero is False:
        return inside.cond
    return None


def required_condition(restriction: DomainRestriction) -> Boolean:
    region = region_condition(restriction.zero)
    if region is None:
        return Ne(restriction.zero, Integer(0))
    return Not(region) if region.has(Contains) else Not(region).to_nnf()


def active_restrictions(
    restrictions: Sequence[DomainRestriction], targets: Sequence[Basic]
) -> list[DomainRestriction]:
    return [
        restriction
        for restriction in restrictions
        if restriction.zero.free_symbols
        and restriction.nonfinite_bindings is None
        and restriction.condition != false
        and not any(target.has(restriction.term) for target in targets)
    ]


def applies_at(restriction: DomainRestriction, point: Mapping[Symbol, Expr]) -> bool:
    return _undefined_at(restriction, point) != false


def is_excluded(restrictions: Sequence[DomainRestriction], point: Mapping[Symbol, Expr]) -> bool:
    return any(applies_at(restriction, point) for restriction in restrictions)


def undefined_condition(
    restrictions: Sequence[DomainRestriction],
    point: Mapping[Symbol, Expr],
    *,
    substitute_integral: Callable[[Expr], SymbolicValue] | None = None,
) -> Boolean:
    return Or(
        *(
            _undefined_at(restriction, point, substitute_integral=substitute_integral)
            for restriction in restrictions
        )
    )


def _undefined_at(
    restriction: DomainRestriction,
    point: Mapping[Symbol, Expr],
    *,
    substitute_integral: Callable[[Expr], SymbolicValue] | None = None,
) -> Boolean:
    reached = condition_at(restriction.condition, point)
    if reached == false:
        return false
    try:
        if restriction.nonfinite_bindings is not None:
            bindings = compose_symbol_substitutions(
                restriction.term.free_symbols, restriction.nonfinite_bindings, point
            )
            preserved = substitute_operation_operands(restriction.term, dict(bindings))
            return And(
                reached, true if preserved.has(AccumBounds) else undefined_branches(preserved)
            )
        if (region := region_condition(restriction.zero)) is not None:
            return And(reached, condition_at(region, point))
        if any(value.is_finite is False and value != zoo for value in point.values()):
            original = substitute_symbols(restriction.term, point)
            return And(reached, undefined_branches(original))
        zero = (
            substitute_integral(restriction.zero)
            if substitute_integral is not None and restriction.zero.has(Integral)
            else substitute_symbols(restriction.zero, point)
        )
    except TypeError:
        return reached
    if not isinstance(zero, Expr):
        return false
    return And(reached, undefined_branches(zero, vanishing=True))


def _localize(restriction: DomainRestriction, unknowns: set[Symbol]) -> list[DomainRestriction]:
    involved = restriction.zero.free_symbols & unknowns
    if len(involved) != 1 or not restriction.condition.free_symbols & involved:
        return [restriction]
    (symbol,) = involved
    points = restriction_points(restriction, symbol)
    if not isinstance(points, FiniteSet):
        return [restriction]
    return [
        DomainRestriction(term=restriction.term, zero=symbol - point, condition=condition)
        for point in points.args
        if (condition := condition_at(restriction.condition, {symbol: point})) != false
    ]


def _gamma_poles(argument: Basic, symbol: Symbol, domain: Set) -> Set | None:
    if not isinstance(argument, Expr):
        return None
    index = Dummy("n", integer=True, nonnegative=True)
    points = zero_set(argument + index, symbol, domain=domain)
    if not isinstance(points, FiniteSet):
        return None
    return Union(*(ImageSet(Lambda(index, point), S.Naturals0) for point in points.args))


def region_restriction(region: Boolean) -> DomainRestriction:
    zero = Piecewise((Integer(0), region), (Integer(1), true))
    return DomainRestriction(term=zero, zero=zero)


def record_restriction(
    restrictions: list[DomainRestriction], restriction: DomainRestriction
) -> None:
    restriction = keep_conditional_restrictions([restriction])[0]
    if (
        (restriction.zero.free_symbols or restriction.substitution_symbols)
        and restriction.condition != false
        and restriction not in restrictions
    ):
        restrictions.append(restriction)
