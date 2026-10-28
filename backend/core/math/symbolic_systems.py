"""SoAI - Symbolic solving of equation systems with honest completeness [backend/core/math/symbolic_systems.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import itertools
import math
from typing import TYPE_CHECKING

from sympy import (
    Basic,
    Dict,
    Expr,
    FiniteSet,
    Float,
    Poly,
    S,
    Symbol,
    Tuple,
    fraction,
    nonlinsolve,
    solve,
    sstr,
    together,
)
from sympy.logic.boolalg import Boolean

from core.math.result_projection import (
    OUTCOME_INFINITELY_MANY,
    OUTCOME_NO_SOLUTION,
    OUTCOME_PARTIAL_SOLUTIONS,
    OUTCOME_SOLUTIONS,
    OUTCOME_UNDETERMINED,
)
from core.math.symbolic_domain import active_restrictions, extend_restrictions, undefined_condition
from core.math.symbolic_exclusions import describe_exclusions
from core.math.symbolic_solution_checks import solution_validity
from core.math.symbolic_solution_sets import (
    all_values,
    as_expression,
    no_solution,
    solve_single_unknown,
    undetermined,
)
from core.math.symbolic_values import SymbolicOutcome, require_expressions

if TYPE_CHECKING:
    from collections.abc import Sequence

    from core.math.symbolic_values import DomainRestriction

__all__ = (
    "is_polynomial_in",
    "solve_system",
)

_MAX_COMBINED_SOLUTIONS = 64
_FAMILY_NOTE = "unknowns that are missing or appear on the right side are free, subject to each solution's constraints"


def is_polynomial_in(target: Expr | Boolean, unknowns: Sequence[Symbol]) -> bool:
    numerator, _denominator = fraction(together(as_expression(target)))
    return numerator.is_polynomial(*unknowns)


def solve_system(
    targets: Sequence[Expr | Boolean],
    unknowns: Sequence[Symbol],
    restrictions: Sequence[DomainRestriction],
) -> SymbolicOutcome:
    active = active_restrictions(restrictions, targets)
    decoupled = _solve_decoupled(targets, unknowns, active)
    if decoupled is not None:
        return decoupled
    complete = all(is_polynomial_in(target, unknowns) for target in targets)
    found: list[dict[Symbol, Expr]] | Boolean
    nonlinear = complete and any(
        Poly(fraction(together(as_expression(target)))[0], *unknowns).total_degree() > 1
        for target in targets
    )
    if nonlinear:
        solved = nonlinsolve([as_expression(target) for target in targets], list(unknowns))
        if solved == S.EmptySet:
            return no_solution(system=True)
        if not isinstance(solved, FiniteSet) or any(
            not isinstance(solution, Tuple)
            or not all(isinstance(value, Expr) for value in solution.args)
            for solution in solved.args
        ):
            return undetermined("the system solver could not express every solution family")
        found = [
            {
                symbol: value
                for symbol, value in zip(unknowns, require_expressions(solution.args), strict=True)
                if symbol != value
            }
            for solution in solved.args
        ]
    else:
        found = solve(list(targets), list(unknowns), dict=True)
    if isinstance(found, Boolean):
        return all_values(unknowns, active) if bool(found) else no_solution(system=True)
    checked = [
        (solution, validity)
        for solution in found
        if undefined_condition(active, solution) != S.true
        and (validity := _point_validity(targets, solution)) is not None
    ]
    solutions = [solution for solution, _validity in checked]
    item_restrictions = tuple(validity for _solution, validity in checked)
    if not solutions:
        if complete:
            return no_solution(system=True)
        return undetermined(
            "the solver found no solution but could not prove that none exists, because the equations are not polynomial"
        )
    items = tuple(Dict(solution) for solution in solutions)
    unknown_set = set(unknowns)
    families = any(
        set(solution) != unknown_set
        or any(value.free_symbols & unknown_set for value in solution.values())
        for solution in solutions
    )
    family = _family_note(unknowns, restrictions) if families else ""
    if not complete:
        detail = f"; {family}" if family else ""
        return SymbolicOutcome(
            outcome=OUTCOME_PARTIAL_SOLUTIONS,
            text=sstr(list(items)),
            note=f"the solver found these solutions but could not prove that there are no others, because the equations are not polynomial{detail}",
            items=items,
            item_restrictions=item_restrictions,
        )
    if families:
        return SymbolicOutcome(
            outcome=OUTCOME_INFINITELY_MANY,
            text=sstr(list(items)),
            note=f"infinitely many solutions: {family}",
            items=items,
            item_restrictions=item_restrictions,
        )
    return SymbolicOutcome(
        outcome=OUTCOME_SOLUTIONS,
        text=sstr(list(items)),
        note="all solutions of the system, including complex ones",
        items=items,
        item_restrictions=item_restrictions,
    )


def _point_validity(
    targets: Sequence[Expr | Boolean], point: dict[Symbol, Expr]
) -> tuple[DomainRestriction, ...] | None:
    combined: list[DomainRestriction] = []
    for target in targets:
        validity = solution_validity(as_expression(target), point)
        if validity is None:
            return None
        extend_restrictions(combined, validity)
    return tuple(combined)


def _family_note(unknowns: Sequence[Symbol], restrictions: Sequence[DomainRestriction]) -> str:
    excluded = describe_exclusions(unknowns, restrictions)
    if not excluded:
        return _FAMILY_NOTE
    return f"{_FAMILY_NOTE}; values with {excluded} are excluded because the original expression is undefined there"


def _solve_decoupled(
    targets: Sequence[Expr | Boolean],
    unknowns: Sequence[Symbol],
    restrictions: Sequence[DomainRestriction],
) -> SymbolicOutcome | None:
    unknown_set = set(unknowns)
    equations: dict[Symbol, Expr] = {}
    for target in targets:
        involved = target.free_symbols & unknown_set
        if len(involved) != 1:
            return None
        (symbol,) = involved
        if symbol in equations:
            return None
        equations[symbol] = as_expression(target)
    if any(len(item.zero.free_symbols & unknown_set) > 1 for item in restrictions):
        return None
    parts = {
        symbol: solve_single_unknown(expression, symbol, restrictions)
        for symbol, expression in equations.items()
    }
    free = {
        unknown: all_values([unknown], restrictions)
        for unknown in unknowns
        if unknown not in equations
    }
    return _combine_parts(parts, free, unknowns)


def _combine_parts(
    parts: dict[Symbol, SymbolicOutcome],
    free: dict[Symbol, SymbolicOutcome],
    unknowns: Sequence[Symbol],
) -> SymbolicOutcome:
    for symbol, part in parts.items():
        if part.outcome == OUTCOME_NO_SOLUTION:
            return SymbolicOutcome(
                outcome=OUTCOME_NO_SOLUTION,
                text="no solution",
                note=f"no value of {symbol} satisfies its equation ({part.note}), so the system has no solution",
            )
    details = "; ".join(f"{symbol}: {part.note}" for symbol, part in parts.items())
    note = f"the equations are independent, so each unknown is solved separately: {details}"
    outcomes = {part.outcome for part in parts.values()}
    count = math.prod(len(part.items) for part in parts.values())
    listed = all(part.items for part in parts.values())
    if (
        listed
        and not free
        and outcomes <= {OUTCOME_SOLUTIONS, OUTCOME_PARTIAL_SOLUTIONS}
        and count <= _MAX_COMBINED_SOLUTIONS
    ):
        symbols = list(parts)
        choices = [
            [(item, part.restrictions_of(item)) for item in part.items if isinstance(item, Expr)]
            for part in parts.values()
        ]
        combinations = list(itertools.product(*choices))
        items = tuple(
            Dict(dict(zip(symbols, (item for item, _kept in combination), strict=True)))
            for combination in combinations
        )
        outcome = (
            OUTCOME_SOLUTIONS if outcomes == {OUTCOME_SOLUTIONS} else OUTCOME_PARTIAL_SOLUTIONS
        )
        return SymbolicOutcome(
            outcome=outcome,
            text=sstr(list(items)),
            note=note,
            items=items,
            item_restrictions=tuple(
                tuple(kept for _item, restrictions in combination for kept in restrictions)
                for combination in combinations
            ),
        )
    every_part = {**parts, **free}
    texts = [f"{symbol}: {every_part[symbol].text}" for symbol in unknowns]
    if free:
        unrestricted = ", ".join(
            sstr(symbol) for symbol, part in free.items() if part.outcome != OUTCOME_INFINITELY_MANY
        )
        restricted = "; ".join(
            f"{symbol}: {part.note}"
            for symbol, part in free.items()
            if part.outcome == OUTCOME_INFINITELY_MANY
        )
        note = "; ".join(
            item
            for item in (
                note,
                f"{unrestricted} can take any value" if unrestricted else "",
                restricted,
            )
            if item
        )
    if OUTCOME_UNDETERMINED in outcomes:
        outcome = OUTCOME_UNDETERMINED
    elif OUTCOME_PARTIAL_SOLUTIONS in outcomes:
        outcome = OUTCOME_PARTIAL_SOLUTIONS
    elif free or outcomes != {OUTCOME_SOLUTIONS}:
        outcome = OUTCOME_INFINITELY_MANY
    else:
        outcome = OUTCOME_SOLUTIONS
    approximate_numbers = {
        number
        for part in every_part.values()
        for item in part.items
        if isinstance(item, Basic)
        for number in item.atoms(Float)
    }
    approximate_numbers.update(
        number for part in every_part.values() for number in part.approximate_numbers
    )
    return SymbolicOutcome(
        outcome=outcome,
        text="; ".join(texts),
        note=note,
        approximate_numbers=tuple(approximate_numbers),
    )
