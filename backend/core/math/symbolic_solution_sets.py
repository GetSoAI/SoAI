"""SoAI - Solution sets of one equation in one unknown, with excluded points [backend/core/math/symbolic_solution_sets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from sympy import (
    Basic,
    Complement,
    ConditionSet,
    Dict,
    Equality,
    Expr,
    FiniteSet,
    Float,
    ImageSet,
    S,
    Symbol,
    default_sort_key,
    solve,
    sstr,
)
from sympy.logic.boolalg import Boolean

from core.math.result_projection import (
    OUTCOME_ALL_VALUES,
    OUTCOME_CONDITIONAL,
    OUTCOME_INFINITELY_MANY,
    OUTCOME_NO_SOLUTION,
    OUTCOME_PARTIAL_SOLUTIONS,
    OUTCOME_SOLUTIONS,
    OUTCOME_UNDETERMINED,
)
from core.math.symbolic_domain import (
    active_restrictions,
    describe_condition,
    is_excluded,
    substitute_restrictions,
)
from core.math.symbolic_exclusions import (
    describe_exclusions,
    describe_set,
    excluded_points,
)
from core.math.symbolic_solution_checks import as_relations, solution_validity
from core.math.symbolic_values import SYMBOLIC_FAILURES, SymbolicOutcome
from core.math.symbolic_vanishing import zero_set

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sympy import Set

    from core.math.symbolic_values import DomainRestriction, Substitution, SymbolicValue

__all__ = (
    "all_values",
    "as_expression",
    "attach_item_restrictions",
    "conditional_outcome",
    "no_solution",
    "solution_point",
    "solve_single_unknown",
    "substitute_target",
    "undetermined",
)


def as_expression(target: Expr | Boolean) -> Expr:
    if isinstance(target, Equality):
        return target.lhs - target.rhs
    if isinstance(target, Expr):
        return target
    raise ValueError("argument 1 must be an equation such as x**2 == 4 or an expression")


def conditional_outcome(cases: Sequence[tuple[str, SymbolicOutcome]]) -> SymbolicOutcome:
    return SymbolicOutcome(
        outcome=OUTCOME_CONDITIONAL,
        text="; ".join(f"{_case_text(case)} when {condition}" for condition, case in cases),
        note="the solutions depend on the parameters, so each case states the condition it needs",
        cases=tuple(cases),
    )


def substitute_target(target: Expr | Boolean, values: Substitution) -> Expr | Boolean:
    result = target.subs(values)
    if isinstance(result, Expr | Boolean):
        return result
    raise ValueError("substituting a parameter value produced an unsupported value")


def no_solution(*, system: bool, real_only: bool = False) -> SymbolicOutcome:
    if system:
        note = "the equations contradict each other, so no values satisfy all of them"
    elif real_only:
        note = "no real value satisfies the equation"
    else:
        note = "no value satisfies the equation, not even a complex one"
    return SymbolicOutcome(outcome=OUTCOME_NO_SOLUTION, text="no solution", note=note)


def undetermined(reason: str) -> SymbolicOutcome:
    return SymbolicOutcome(
        outcome=OUTCOME_UNDETERMINED,
        text="unknown",
        note=f"{reason}; rewrite the equation or estimate a root numerically",
    )


def all_values(
    unknowns: Sequence[Symbol], restrictions: Sequence[DomainRestriction], *, suffix: str = ""
) -> SymbolicOutcome:
    names = ", ".join(sstr(unknown) for unknown in unknowns)
    excluded = describe_exclusions(unknowns, restrictions)
    if not excluded:
        return SymbolicOutcome(
            outcome=OUTCOME_ALL_VALUES,
            text="all values",
            note=f"the equation holds for every value of {names}{suffix}",
        )
    return SymbolicOutcome(
        outcome=OUTCOME_INFINITELY_MANY,
        text=f"all values except {excluded}",
        note=f"the equation holds for every value of {names}{suffix} except {excluded}, where the original expression is undefined",
    )


def solve_single_unknown(
    expression: Expr, symbol: Symbol, restrictions: Sequence[DomainRestriction]
) -> SymbolicOutcome:
    try:
        solution_set = zero_set(expression, symbol, domain=S.Complexes)
    except SYMBOLIC_FAILURES:
        return _describe_solution_set(
            zero_set(expression, symbol, domain=S.Reals),
            expression,
            symbol,
            restrictions,
            real_only=True,
        )
    return _describe_solution_set(solution_set, expression, symbol, restrictions, real_only=False)


def _case_text(case: SymbolicOutcome) -> str:
    return f"({case.text})" if case.outcome == OUTCOME_CONDITIONAL else case.text


def _describe_solution_set(
    solution_set: Set,
    expression: Expr,
    symbol: Symbol,
    restrictions: Sequence[DomainRestriction],
    *,
    real_only: bool,
    requirement: Boolean = S.true,
) -> SymbolicOutcome:
    scope = " over the real numbers" if real_only else ""
    if isinstance(solution_set, ConditionSet):
        if symbol in solution_set.condition.free_symbols:
            return _fallback_solutions(expression, symbol, restrictions)
        return _describe_solution_set(
            solution_set.base_set,
            expression,
            symbol,
            restrictions,
            real_only=real_only,
            requirement=as_relations(solution_set.condition),
        )
    condition = "" if requirement == S.true else f" when {describe_condition(requirement)}"
    if isinstance(solution_set, Complement):
        base, removed = solution_set.args
        if isinstance(base, FiniteSet):
            solution_set = FiniteSet(
                *(value for value in base.args if removed.contains(value) != S.true)
            )
    if solution_set == S.EmptySet:
        return no_solution(system=False, real_only=real_only)
    if solution_set in (S.Complexes, S.Reals):
        return all_values([symbol], restrictions, suffix=f"{scope}{condition}")
    if isinstance(solution_set, FiniteSet):
        return _finite_solutions(
            solution_set,
            expression,
            symbol,
            restrictions,
            real_only=real_only,
            requirement=requirement,
            condition=condition,
        )
    text = describe_set(solution_set, symbol)
    excluded = excluded_points(restrictions, symbol)
    if excluded:
        text = f"{text}, except {excluded}"
    exclusion = (
        f", excluding {excluded} where the original expression is undefined" if excluded else ""
    )
    if solution_set.is_finite_set is False or solution_set.has(ImageSet):
        families = scope or ", including complex ones"
        return SymbolicOutcome(
            outcome=OUTCOME_INFINITELY_MANY,
            text=text,
            note=f"infinitely many solutions{families}{condition}{exclusion}",
            approximate_numbers=tuple(solution_set.atoms(Float)),
        )
    return SymbolicOutcome(
        outcome=OUTCOME_SOLUTIONS,
        text=text,
        note=f"all solutions{scope}{condition}{exclusion}",
        approximate_numbers=tuple(solution_set.atoms(Float)),
    )


def _finite_solutions(
    solution_set: FiniteSet,
    expression: Expr,
    symbol: Symbol,
    restrictions: Sequence[DomainRestriction],
    *,
    real_only: bool,
    requirement: Boolean,
    condition: str,
) -> SymbolicOutcome:
    candidates = sorted(solution_set.args, key=default_sort_key)
    validity = {
        value: solution_validity(expression, {symbol: value}, requirement)
        for value in candidates
        if not is_excluded(restrictions, {symbol: value})
    }
    solutions = tuple(value for value, valid in validity.items() if valid is not None)
    if not solutions:
        return SymbolicOutcome(
            outcome=OUTCOME_NO_SOLUTION,
            text="no solution",
            note="no candidate is defined and satisfies the original equation, so there is no solution",
        )
    completeness = "all real solutions" if real_only else "all solutions, including complex ones"
    removed = (
        "; candidates that were undefined or did not satisfy the original equation were removed"
        if len(solutions) < len(candidates)
        else ""
    )
    return SymbolicOutcome(
        outcome=OUTCOME_SOLUTIONS,
        text=sstr(list(solutions)),
        note=f"{completeness}{condition}{removed}",
        items=solutions,
        item_restrictions=tuple(validity[value] or () for value in solutions),
    )


def solution_point(item: SymbolicValue, unknowns: Sequence[Symbol]) -> dict[Symbol, Expr] | None:
    if isinstance(item, Dict):
        return dict(item.items())
    if isinstance(item, Expr) and len(unknowns) == 1:
        return {unknowns[0]: item}
    return None


def attach_item_restrictions(
    outcome: SymbolicOutcome,
    unknowns: Sequence[Symbol],
    restrictions: Sequence[DomainRestriction],
) -> SymbolicOutcome:
    translated = tuple(
        (
            *outcome.restrictions_of(item),
            *(
                active_restrictions(substitute_restrictions(restrictions, point), [item])
                if isinstance(item, Basic) and (point := solution_point(item, unknowns))
                else ()
            ),
        )
        for item in outcome.items
    )
    if not any(translated):
        return outcome
    return replace(outcome, item_restrictions=translated)


def _fallback_solutions(
    expression: Expr, symbol: Symbol, restrictions: Sequence[DomainRestriction]
) -> SymbolicOutcome:
    try:
        found = solve(expression, symbol, dict=True)
    except SYMBOLIC_FAILURES:
        found = []
    candidates = [] if isinstance(found, Boolean) else found
    validity = {
        solution[symbol]: solution_validity(expression, solution)
        for solution in candidates
        if symbol in solution and not is_excluded(restrictions, solution)
    }
    solutions = tuple(
        sorted(
            (value for value, valid in validity.items() if valid is not None), key=default_sort_key
        )
    )
    if not solutions:
        return undetermined("the solver could not determine the solutions")
    return SymbolicOutcome(
        outcome=OUTCOME_PARTIAL_SOLUTIONS,
        text=sstr(list(solutions)),
        note="the solver found these solutions but could not prove that there are no others",
        items=solutions,
        item_restrictions=tuple(validity[value] or () for value in solutions),
    )
