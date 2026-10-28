"""SoAI - Case analysis for equations whose solutions depend on parameters [backend/core/math/symbolic_parameter_cases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from sympy import (
    Basic,
    Eq,
    Expr,
    Poly,
    Rel,
    Symbol,
    default_sort_key,
    false,
    fraction,
    linear_eq_to_matrix,
    nan,
    solve,
    sstr,
    together,
    true,
    zoo,
)
from sympy.logic.boolalg import Boolean

from core.math.result_projection import (
    OUTCOME_NO_SOLUTION,
    OUTCOME_PARTIAL_SOLUTIONS,
    OUTCOME_SOLUTIONS,
    OUTCOME_UNDETERMINED,
)
from core.math.symbolic_domain import (
    active_restrictions,
    applies_at,
    describe_condition,
    substitute_restrictions,
)
from core.math.symbolic_solution_sets import (
    as_expression,
    conditional_outcome,
    solution_point,
    substitute_target,
    undetermined,
)
from core.math.symbolic_systems import is_polynomial_in
from core.math.symbolic_undefined import condition_at
from core.math.symbolic_values import SYMBOLIC_FAILURES, SymbolicOutcome
from core.math.symbolic_vanishing import zero_factors

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from core.math.symbolic_values import DomainRestriction

    type Assumptions = tuple[Boolean, ...]
    type CaseSolver = Callable[
        [list[Expr | Boolean], list[DomainRestriction], Assumptions], SymbolicOutcome
    ]

__all__ = (
    "critical_parameter_values",
    "resolve_parameter_cases",
)

_MAX_PARAMETER_CASES = 4


def resolve_parameter_cases(
    targets: Sequence[Expr | Boolean],
    unknowns: Sequence[Symbol],
    restrictions: Sequence[DomainRestriction],
    generic: SymbolicOutcome,
    assumptions: Assumptions,
    *,
    solve_case: CaseSolver | None,
) -> SymbolicOutcome:
    active = active_restrictions(restrictions, targets)
    zeros = [restriction.zero for restriction in active]
    branches = [restriction.condition for restriction in active]
    parameters = sorted(
        {symbol for item in (*targets, *zeros, *branches) for symbol in item.free_symbols}
        - set(unknowns),
        key=default_sort_key,
    )
    if not parameters:
        return generic
    if solve_case is None:
        return _unproven(generic, parameters)
    conditions, proven = _critical_conditions(targets, unknowns, zeros, generic)
    joint: list[dict[Symbol, Expr]] = []
    if not proven and generic.outcome == OUTCOME_NO_SOLUTION:
        joint, proven = _joint_parameter_values(targets, unknowns, parameters)
    candidates, solved = critical_parameter_values(conditions, joint)
    critical = [values for values in candidates if _admits(assumptions, values)]
    generic_case = generic if proven and solved else _unproven(generic, parameters)
    if not critical:
        return generic_case
    cases = [(_generic_condition(critical), generic_case)]
    cases.extend(
        (
            _case_condition(values),
            _special_case(targets, unknowns, restrictions, values, assumptions, solve_case),
        )
        for values in critical
    )
    return conditional_outcome(cases)


def _critical_conditions(
    targets: Sequence[Expr | Boolean],
    unknowns: Sequence[Symbol],
    zeros: Sequence[Expr],
    generic: SymbolicOutcome,
) -> tuple[list[Expr], bool]:
    unknown_set = set(unknowns)
    singular = list(zeros)
    numerators: list[Expr] = []
    for target in targets:
        numerator, denominator = fraction(together(as_expression(target)))
        singular.append(denominator)
        numerators.append(numerator)
    conditions: list[Basic] = [*singular]
    for term in singular:
        conditions.extend(zero_factors(term))
        if term.free_symbols & unknown_set and term.is_polynomial(*unknowns):
            conditions.append(Poly(term, *unknowns).LC())
    conditions.extend(
        numerator for numerator in numerators if not numerator.free_symbols & unknown_set
    )
    involved = [numerator.free_symbols & unknown_set for numerator in numerators]
    pivots = [next(iter(symbols)) for symbols in involved if len(symbols) == 1]
    proven = True
    if len(pivots) == len([symbols for symbols in involved if symbols]) == len(set(pivots)):
        for numerator, symbols in zip(numerators, involved, strict=True):
            if not symbols:
                continue
            (symbol,) = symbols
            if numerator.is_polynomial(symbol):
                conditions.append(Poly(numerator, symbol).LC())
            else:
                proven = False
    elif len(numerators) == len(unknowns) and all(
        numerator.is_polynomial(*unknowns) and Poly(numerator, *unknowns).total_degree() <= 1
        for numerator in numerators
    ):
        matrix, _constants = linear_eq_to_matrix(numerators, list(unknowns))
        determinant = matrix.det()
        conditions.append(determinant)
        proven = determinant.is_zero is not True
    else:
        proven = False
    for point in _solution_points(generic, unknowns):
        conditions.extend(fraction(together(value))[1] for value in point.values())
        conditions.extend(item.subs(point) for item in singular if item.free_symbols & unknown_set)
    return [
        condition
        for condition in conditions
        if isinstance(condition, Expr)
        and condition.free_symbols
        and not condition.free_symbols & unknown_set
    ], proven


def _solution_points(
    generic: SymbolicOutcome, unknowns: Sequence[Symbol]
) -> list[dict[Symbol, Expr]]:
    return [
        point for item in generic.items if (point := solution_point(item, unknowns)) is not None
    ]


def _joint_parameter_values(
    targets: Sequence[Expr | Boolean], unknowns: Sequence[Symbol], parameters: Sequence[Symbol]
) -> tuple[list[dict[Symbol, Expr]], bool]:
    symbols = [*unknowns, *parameters]
    if not all(is_polynomial_in(target, symbols) for target in targets):
        return [], False
    try:
        solutions = solve(list(targets), symbols, dict=True)
    except SYMBOLIC_FAILURES:
        return [], False
    if isinstance(solutions, Boolean):
        return [], False
    unknown_set = set(unknowns)
    found: list[dict[Symbol, Expr]] = []
    for solution in solutions:
        values = {symbol: value for symbol, value in solution.items() if symbol in parameters}
        if not values or any(value.free_symbols & unknown_set for value in values.values()):
            return [], False
        found.append(values)
    return found, True


def critical_parameter_values(
    conditions: Sequence[Expr], seeds: Sequence[dict[Symbol, Expr]]
) -> tuple[list[dict[Symbol, Expr]], bool]:
    found: list[dict[Symbol, Expr]] = []
    seen: set[frozenset[tuple[Symbol, Expr]]] = set()
    complete = True
    candidates = [*seeds]
    for condition in conditions:
        symbols = sorted(condition.free_symbols, key=default_sort_key)
        if not condition.is_polynomial(*symbols):
            complete = False
        try:
            solutions = solve(condition, *symbols, dict=True)
        except SYMBOLIC_FAILURES:
            complete = False
            continue
        if isinstance(solutions, Boolean):
            complete = False
            continue
        candidates.extend(solutions)
    for values in candidates:
        key = frozenset(values.items())
        if key not in seen:
            seen.add(key)
            found.append(values)
    if len(found) > _MAX_PARAMETER_CASES:
        return found[:_MAX_PARAMETER_CASES], False
    return found, complete


def _special_case(
    targets: Sequence[Expr | Boolean],
    unknowns: Sequence[Symbol],
    restrictions: Sequence[DomainRestriction],
    values: dict[Symbol, Expr],
    assumptions: Assumptions,
    solve_case: CaseSolver,
) -> SymbolicOutcome:
    substituted = [substitute_target(target, values) for target in targets]
    undefined = SymbolicOutcome(
        outcome=OUTCOME_NO_SOLUTION,
        text="no solution",
        note="the original expression is undefined for these parameter values",
    )
    if any(target.has(zoo, nan) for target in substituted):
        return undefined
    kept: list[DomainRestriction] = []
    for restriction in substitute_restrictions(restrictions, values):
        condition = restriction.condition
        if restriction.zero.free_symbols or not applies_at(restriction, {}):
            kept.append(restriction)
            continue
        if not condition.free_symbols & set(unknowns):
            return undefined
        if isinstance(condition, Rel) and condition.rel_op == "==":
            kept.append(replace(restriction, zero=condition.lhs - condition.rhs, condition=true))
        elif isinstance(condition, Rel) and condition.rel_op == "!=":
            substituted.append(Eq(condition.lhs, condition.rhs))
        else:
            return undetermined(
                f"for these parameter values the original expression is undefined wherever {describe_condition(condition)}, which the solver cannot combine with the equations"
            )
    remaining = tuple(
        condition
        for assumption in assumptions
        if (condition := condition_at(assumption, values)) != true
    )
    return solve_case(substituted, kept, remaining)


def _admits(assumptions: Assumptions, values: dict[Symbol, Expr]) -> bool:
    return all(condition_at(assumption, values) != false for assumption in assumptions)


def _unproven(generic: SymbolicOutcome, parameters: Sequence[Symbol]) -> SymbolicOutcome:
    names = ", ".join(sstr(parameter) for parameter in parameters)
    caveat = f"this holds for generic values of {names}; particular values of {names} were not all checked and can behave differently"
    note = f"{generic.note}; {caveat}"
    if generic.outcome == OUTCOME_SOLUTIONS:
        return replace(generic, outcome=OUTCOME_PARTIAL_SOLUTIONS, note=note)
    if generic.outcome == OUTCOME_NO_SOLUTION:
        return SymbolicOutcome(
            outcome=OUTCOME_UNDETERMINED, text=f"no solution for generic {names}", note=note
        )
    return replace(generic, note=note)


def _case_condition(values: dict[Symbol, Expr]) -> str:
    return " and ".join(
        f"{sstr(symbol)} == {sstr(value)}"
        for symbol, value in sorted(values.items(), key=lambda pair: default_sort_key(pair[0]))
    )


def _generic_condition(critical: Sequence[dict[Symbol, Expr]]) -> str:
    negations: list[str] = []
    for values in critical:
        if len(values) == 1:
            ((symbol, value),) = values.items()
            negations.append(f"{sstr(symbol)} != {sstr(value)}")
        else:
            negations.append(f"not ({_case_condition(values)})")
    return " and ".join(negations)
