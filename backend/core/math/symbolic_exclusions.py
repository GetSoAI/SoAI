"""SoAI - Descriptions of points excluded from symbolic results [backend/core/math/symbolic_exclusions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sympy import (
    Complement,
    ConditionSet,
    FiniteSet,
    ImageSet,
    Lambda,
    S,
    Symbol,
    Union,
    sstr,
)
from sympy.logic.boolalg import Boolean

from core.math.symbolic_domain import (
    describe_condition,
    region_condition,
    required_condition,
    restriction_points,
)
from core.math.symbolic_undefined import condition_at

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sympy import Set

    from core.math.symbolic_values import DomainRestriction

__all__ = (
    "describe_constraints",
    "describe_exclusions",
    "describe_set",
    "excluded_points",
)

_INDEX_NAMES = ("n", "k", "m", "j")


@dataclass(frozen=True, slots=True)
class _Exclusion:
    subject: str
    value: str
    condition: Boolean
    located: bool
    joiner: str = ", "


def describe_exclusions(
    unknowns: Sequence[Symbol], restrictions: Sequence[DomainRestriction]
) -> str:
    if len(unknowns) == 1:
        return excluded_points(restrictions, unknowns[0])
    return " or ".join(
        _restriction_text(item) for item in restrictions if item.zero.free_symbols & set(unknowns)
    )


def describe_constraints(restrictions: Sequence[DomainRestriction]) -> tuple[str, ...]:
    texts: list[str] = []
    for restriction in restrictions:
        region = region_condition(restriction.zero)
        symbols = restriction.zero.free_symbols
        symbol = next(iter(symbols)) if len(symbols) == 1 else None
        candidates = (
            [
                f"{describe_condition(required_condition(restriction))}{_condition_suffix(restriction.condition, ' when ')}"
            ]
            if region is not None
            else [
                f"{exclusion.subject} != {exclusion.value}{_condition_suffix(exclusion.condition, ' when ')}"
                for exclusion in _exclusions(restriction, symbol)
            ]
        )
        texts.extend(text for text in candidates if text not in texts)
    return tuple(texts)


def excluded_points(restrictions: Sequence[DomainRestriction], symbol: Symbol) -> str:
    descriptions: list[str] = []
    for restriction in restrictions:
        if symbol not in restriction.zero.free_symbols:
            continue
        if region_condition(restriction.zero) is not None:
            descriptions.append(_restriction_text(restriction))
            continue
        exclusions = _exclusions(restriction, symbol)
        located = [exclusion for exclusion in exclusions if exclusion.located]
        if located:
            values = located[0].joiner.join(exclusion.value for exclusion in located)
            descriptions.append(f"{sstr(symbol)} = {values}")
        descriptions.extend(
            f"where {exclusion.subject} == {exclusion.value}{_condition_suffix(exclusion.condition, ' and ')}"
            for exclusion in exclusions
            if not exclusion.located
        )
    return ", and ".join(descriptions)


def _exclusions(restriction: DomainRestriction, symbol: Symbol | None) -> list[_Exclusion]:
    points = None if symbol is None else restriction_points(restriction, symbol)
    if symbol is not None and isinstance(points, FiniteSet):
        return [
            _Exclusion(sstr(symbol), sstr(point), condition, located=condition == S.true)
            for point in points.args
            if (condition := condition_at(restriction.condition, {symbol: point})) != S.false
        ]
    if points == S.EmptySet:
        return []
    if symbol is None or points is None or isinstance(points, ConditionSet):
        return [_Exclusion(sstr(restriction.zero), "0", restriction.condition, located=False)]
    parts = points.args if isinstance(points, Union) else (points,)
    located = restriction.condition == S.true
    return [
        _Exclusion(
            sstr(symbol),
            describe_set(part, symbol),
            restriction.condition,
            located=located,
            joiner=" or ",
        )
        for part in parts
    ]


def _condition_suffix(condition: Boolean, joiner: str) -> str:
    return "" if condition == S.true else f"{joiner}{describe_condition(condition)}"


def _restriction_text(restriction: DomainRestriction) -> str:
    region = region_condition(restriction.zero)
    excluded = (
        f"{sstr(restriction.zero)} == 0"
        if region is None
        else f"where {describe_condition(region)}"
    )
    return f"{excluded}{_condition_suffix(restriction.condition, ' and ')}"


def describe_set(solution_set: Set, unknown: Symbol | None = None) -> str:
    if isinstance(solution_set, Union):
        return " or ".join(describe_set(part, unknown) for part in solution_set.args)
    if isinstance(solution_set, FiniteSet):
        return ", ".join(sstr(value) for value in solution_set.args)
    if isinstance(solution_set, Complement):
        base, removed = solution_set.args
        return f"{describe_set(base, unknown)}, except {describe_set(removed, unknown)}"
    if isinstance(solution_set, ImageSet):
        function, *bases = solution_set.args
        if isinstance(function, Lambda) and bases in ([S.Integers], [S.Naturals0]):
            (variable,) = function.variables
            taken = {symbol.name for symbol in function.expr.free_symbols - {variable}}
            if unknown is not None:
                taken.add(unknown.name)
            index = next((Symbol(name) for name in _INDEX_NAMES if name not in taken), None)
            if index is not None:
                bound = "" if bases == [S.Integers] else " >= 0"
                return f"{sstr(function.expr.subs(variable, index))} for any integer {index}{bound}"
    return sstr(solution_set)
