"""SoAI - Symbolic equation solving with explicit outcomes [backend/core/math/symbolic_solving.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from sympy import (
    ConditionSet,
    Contains,
    Dummy,
    Eq,
    Equality,
    Expr,
    FiniteSet,
    Integer,
    Ne,
    Poly,
    Rel,
    S,
    Symbol,
    default_sort_key,
    reduce_inequalities,
    solve,
)
from sympy.logic.boolalg import And, Boolean, Not, Or

from core.math.symbolic_condition_cases import resolve_condition_cases
from core.math.symbolic_domain import (
    active_restrictions,
    localize_restrictions,
    region_condition,
    required_condition,
    restriction_points,
    undefined_condition,
)
from core.math.symbolic_parameter_cases import resolve_parameter_cases
from core.math.symbolic_regions import connect_condition
from core.math.symbolic_solution_sets import (
    all_values,
    as_expression,
    attach_item_restrictions,
    no_solution,
    solve_single_unknown,
)
from core.math.symbolic_systems import solve_system
from core.math.symbolic_undefined import condition_at
from core.math.symbolic_values import SymbolicOutcome, require_symbol
from core.math.symbolic_vanishing import zero_set

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sympy import Set

    from core.math.symbolic_values import DomainRestriction, SymbolicValue

__all__ = ("solve_equations",)

_MAX_CASE_DEPTH = 3
_CONDITIONAL_EXCLUSION_MESSAGE = "the inequality could not be combined with the points where the original expression is undefined"


def solve_equations(
    equations: SymbolicValue,
    unknowns: SymbolicValue | None = None,
    *,
    excluded: Sequence[DomainRestriction] = (),
) -> SymbolicValue:
    targets = (
        [_equation(item, position=1) for item in equations]
        if isinstance(equations, list)
        else [_equation(equations, position=1)]
    )
    if not targets:
        raise ValueError("argument 1 must contain at least one equation")
    symbols = _unknowns(unknowns)
    if any(_is_inequality(target) for target in targets):
        return _solve_inequalities(targets, symbols, excluded)
    return _solve_targets(targets, list(excluded), (), symbols=symbols, depth=0)


def _solve_targets(
    targets: list[Expr | Boolean],
    restrictions: list[DomainRestriction],
    assumptions: tuple[Boolean, ...],
    *,
    symbols: list[Symbol],
    depth: int,
) -> SymbolicOutcome:
    system = len(targets) > 1
    if any(_is_contradiction(target) for target in targets):
        return no_solution(system=system)
    remaining = [target for target in targets if not _is_identity(target)]
    unknowns = symbols or _infer_unknowns(remaining, active_restrictions(restrictions, targets))
    localized = localize_restrictions(restrictions, unknowns)
    solve_case = (
        partial(_solve_targets, symbols=unknowns, depth=depth + 1)
        if depth < _MAX_CASE_DEPTH
        else None
    )
    split = resolve_condition_cases(
        remaining, unknowns, localized, assumptions, solve_case=solve_case
    )
    if split is not None:
        return split
    active = active_restrictions(localized, targets)
    if not remaining:
        generic = all_values(unknowns, active)
    elif any(not target.free_symbols & set(unknowns) for target in remaining):
        generic = no_solution(system=system)
    elif len(remaining) == 1 and len(unknowns) == 1:
        generic = solve_single_unknown(as_expression(remaining[0]), unknowns[0], active)
    else:
        generic = solve_system(remaining, unknowns, localized)
    return resolve_parameter_cases(
        remaining,
        unknowns,
        localized,
        attach_item_restrictions(generic, unknowns, localized),
        assumptions,
        solve_case=solve_case,
    )


def _infer_unknowns(
    targets: Sequence[Expr | Boolean], restrictions: Sequence[DomainRestriction]
) -> list[Symbol]:
    sources = targets or [restriction.zero for restriction in restrictions]
    return sorted(
        {symbol for source in sources for symbol in source.free_symbols}, key=default_sort_key
    )


def _solve_inequalities(
    targets: list[Expr | Boolean],
    symbols: list[Symbol],
    restrictions: Sequence[DomainRestriction],
) -> Boolean:
    unknowns = symbols or _infer_unknowns(targets, restrictions)
    ordered = any(
        relation.rel_op not in ("==", "!=") for target in targets for relation in target.atoms(Rel)
    )
    complex_conditions = not ordered or any(
        isinstance(target, And | Or | Not) for target in targets
    )
    considered = restrictions if complex_conditions else active_restrictions(restrictions, targets)
    exclusions = _exclusion_constraints(
        considered, unknowns, domain=S.Complexes if complex_conditions else S.Reals
    )
    if complex_conditions:
        condition = And(
            *(Eq(target, Integer(0)) if isinstance(target, Expr) else target for target in targets)
        )
        return And(_solve_boolean_condition(condition, unknowns), *exclusions)
    constraints = [*targets, *exclusions]
    result: list[dict[Symbol, Expr]] | Boolean
    if any(isinstance(target, And | Or | Not) for target in constraints):
        result = _solve_boolean_condition(
            And(
                *(
                    Eq(target, Integer(0)) if isinstance(target, Expr) else target
                    for target in constraints
                )
            ),
            unknowns,
        )
    elif len(constraints) == 1:
        result = solve(constraints[0], *symbols)
    else:
        result = solve(constraints, symbols) if symbols else solve(constraints)
    if isinstance(result, Boolean):
        return And(result, *_parameter_constraints(considered, unknowns))
    raise ValueError("inequalities can be solved for one unknown at a time")


def _solve_boolean_condition(condition: Boolean, unknowns: Sequence[Symbol]) -> Boolean:
    if isinstance(condition, And | Or | Not):
        return connect_condition(
            condition,
            [
                _solve_boolean_condition(part, unknowns)
                for part in condition.args
                if isinstance(part, Boolean)
            ],
        )
    if isinstance(condition, Rel) and condition.rel_op in ("==", "!="):
        involved = [symbol for symbol in unknowns if symbol in condition.free_symbols]
        if not involved:
            return condition
        if len(involved) != 1:
            raise ValueError(
                "each Boolean equation must involve only one unknown; solve coupled equations as a list"
            )
        (symbol,) = involved
        expression = condition.lhs - condition.rhs
        if expression.free_symbols - {symbol} and (
            not expression.is_polynomial(symbol)
            or Poly(expression, symbol).LC().is_zero is not False
        ):
            raise ValueError(
                "the Boolean equation may have additional solutions for special parameter values; substitute values for the parameters or solve its equations separately"
            )
        solutions = zero_set(expression, symbol, domain=S.Complexes)
        if solutions.has(ConditionSet):
            raise ValueError(
                "the complex solutions of this Boolean equation could not be determined; solve its equations separately"
            )
        result = (
            Or(*(Eq(symbol, value) for value in solutions.args))
            if isinstance(solutions, FiniteSet)
            else Contains(symbol, solutions)
        )
        return Not(result) if condition.rel_op == "!=" else result
    return reduce_inequalities([condition], list(unknowns))


def _parameter_constraints(
    restrictions: Sequence[DomainRestriction], unknowns: Sequence[Symbol]
) -> list[Boolean]:
    constraints: list[Boolean] = []
    for restriction in restrictions:
        if restriction.zero.free_symbols & set(unknowns):
            continue
        if restriction.condition != S.true:
            raise ValueError(_CONDITIONAL_EXCLUSION_MESSAGE)
        constraints.append(required_condition(restriction))
    return constraints


def _exclusion_constraints(
    restrictions: Sequence[DomainRestriction], unknowns: Sequence[Symbol], *, domain: Set
) -> list[Boolean]:
    constraints: list[Boolean] = []
    real_unknowns = {symbol: Dummy(symbol.name, real=True) for symbol in unknowns}
    for restriction in restrictions:
        if (
            domain == S.Reals
            and region_condition(restriction.zero) is not None
            and undefined_condition([restriction], real_unknowns) == S.false
        ):
            continue
        involved = [symbol for symbol in unknowns if symbol in restriction.zero.free_symbols]
        if not involved and domain == S.Reals:
            continue
        if len(involved) == 1 and region_condition(restriction.zero) is None:
            (symbol,) = involved
            points = restriction_points(restriction, symbol, domain=domain)
            if points == S.EmptySet:
                continue
            if isinstance(points, FiniteSet):
                for point in points.args:
                    condition = condition_at(restriction.condition, {symbol: point})
                    if condition == S.false:
                        continue
                    if condition != S.true and domain == S.Reals:
                        raise ValueError(_CONDITIONAL_EXCLUSION_MESSAGE)
                    constraints.append(Or(Not(condition), Ne(symbol, point)))
                continue
        if restriction.condition != S.true and domain == S.Reals:
            raise ValueError(_CONDITIONAL_EXCLUSION_MESSAGE)
        constraints.append(Or(Not(restriction.condition), required_condition(restriction)))
    return constraints


def _equation(value: SymbolicValue, *, position: int) -> Expr | Boolean:
    if isinstance(value, Expr | Boolean):
        return value
    raise ValueError(f"argument {position} must be an equation such as x**2 == 4 or an expression")


def _unknowns(value: SymbolicValue | None) -> list[Symbol]:
    if value is None:
        return []
    if isinstance(value, list):
        return [require_symbol(item, position=2) for item in value]
    return [require_symbol(value, position=2)]


def _is_inequality(target: Expr | Boolean) -> bool:
    return isinstance(target, And | Or | Not) or (
        isinstance(target, Rel) and not isinstance(target, Equality)
    )


def _is_identity(target: Expr | Boolean) -> bool:
    return target == S.true or (isinstance(target, Expr) and target.is_zero is True)


def _is_contradiction(target: Expr | Boolean) -> bool:
    if target == S.false:
        return True
    return isinstance(target, Expr) and target.is_number and target.is_zero is False
