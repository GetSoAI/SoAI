"""SoAI - Case splits on conditions that only involve parameters [backend/core/math/symbolic_condition_cases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import And, Basic, Not, Piecewise, Rel, S, default_sort_key, false, true

from core.math.symbolic_domain import (
    active_restrictions,
    describe_condition,
    substitute_restrictions,
)
from core.math.symbolic_solution_sets import conditional_outcome, substitute_target
from core.math.symbolic_values import SYMBOLIC_FAILURES

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sympy import Expr, Symbol
    from sympy.logic.boolalg import Boolean

    from core.math.symbolic_parameter_cases import Assumptions, CaseSolver
    from core.math.symbolic_values import DomainRestriction, SymbolicOutcome

__all__ = ("resolve_condition_cases",)


def resolve_condition_cases(
    targets: Sequence[Expr | Boolean],
    unknowns: Sequence[Symbol],
    restrictions: Sequence[DomainRestriction],
    assumptions: Assumptions,
    *,
    solve_case: CaseSolver | None,
) -> SymbolicOutcome | None:
    relation = _undecided_relation(targets, active_restrictions(restrictions, targets), unknowns)
    if relation is None or solve_case is None:
        return None
    parts = [
        *targets,
        *(part for item in restrictions for part in (item.term, item.zero, item.condition)),
    ]
    cases: list[tuple[str, SymbolicOutcome]] = []
    for condition in (relation, Not(relation)):
        if not _feasible((*assumptions, condition)):
            continue
        decision = _decision(relation, holds=condition == relation, parts=parts)
        case = solve_case(
            [substitute_target(target, decision) for target in targets],
            substitute_restrictions(restrictions, decision),
            (*assumptions, condition),
        )
        shown = condition.canonical if isinstance(condition, Rel) else condition
        cases.append((describe_condition(shown), case))
    if len(cases) == 1:
        return cases[0][1]
    return conditional_outcome(cases) if cases else None


def _undecided_relation(
    targets: Sequence[Expr | Boolean],
    active: Sequence[DomainRestriction],
    unknowns: Sequence[Symbol],
) -> Rel | None:
    sources: list[Basic] = [restriction.condition for restriction in active]
    sources.extend(piecewise for target in targets for piecewise in target.atoms(Piecewise))
    relations = {
        relation.canonical
        for source in sources
        for relation in source.atoms(Rel)
        if relation.free_symbols and not relation.free_symbols & set(unknowns)
    }
    return min(relations, key=default_sort_key, default=None)


def _decision(relation: Rel, *, holds: bool, parts: Sequence[Basic]) -> dict[Basic, Basic]:
    negation = Not(relation)
    canonical = relation.canonical
    negated = negation.canonical if isinstance(negation, Rel) else negation
    decision: dict[Basic, Basic] = {}
    for part in parts:
        for atom in part.atoms(Rel):
            if atom.canonical == canonical:
                decision[atom] = true if holds else false
            elif atom.canonical == negated:
                decision[atom] = false if holds else true
    return decision


def _feasible(conditions: Assumptions) -> bool:
    try:
        return And(*conditions).as_set() != S.EmptySet
    except SYMBOLIC_FAILURES:
        return True
