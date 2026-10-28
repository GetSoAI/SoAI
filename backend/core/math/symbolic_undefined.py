"""SoAI - Where symbolic values and conditions are undefined at a point [backend/core/math/symbolic_undefined.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from sympy import (
    AccumBounds,
    Basic,
    Contains,
    Dummy,
    Expr,
    Piecewise,
    Rel,
    S,
    false,
    nan,
    oo,
    piecewise_fold,
    simplify,
    true,
    zoo,
)
from sympy.logic.boolalg import And, Boolean, Not, Or

from core.math.symbolic_bindings import substitute_operation_operands, substitute_symbols
from core.math.symbolic_precision import evaluate_symbolic_precision

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from sympy import Symbol

    from core.math.symbolic_values import Substitution, SymbolicValue

__all__ = (
    "absorb_undefined",
    "condition_at",
    "decided_relations",
    "finite_complex_condition",
    "numerically_zero",
    "reports_undefined",
    "undefined_branches",
    "undefined_when",
)

_MAX_UNDECIDED_RELATIONS = 3
_NUMERIC_DIGITS = 50


def condition_at(condition: Boolean, point: Substitution) -> Boolean:
    try:
        masks: dict[Basic, Basic] = {}
        memberships: dict[Basic, Basic] = {}
        for membership in condition.atoms(Contains):
            element, domain = membership.args
            if domain != S.Complexes or element == nan:
                continue
            marker = Dummy("finite_complex")
            masks[membership] = marker
            try:
                memberships[marker] = finite_complex_condition(substitute_symbols(element, point))
            except (TypeError, ValueError, ArithmeticError):
                memberships[marker] = false
        resolved = substitute_symbols(condition.xreplace(masks), point).xreplace(memberships)
    except TypeError:
        return _possible_condition(condition, point)
    return decided_relations(resolved) if isinstance(resolved, Boolean) else true


def finite_complex_condition(value: Basic) -> Boolean:
    if not isinstance(value, Expr) or value.has(AccumBounds):
        return false
    if not value.free_symbols and value.has(oo):
        value = substitute_operation_operands(value, {})
    return Contains(value, S.Complexes, evaluate=not value.free_symbols)


def decided_relations(condition: Boolean) -> Boolean:
    decided: dict[Basic, Basic] = {}
    for relation in condition.atoms(Rel):
        if relation.free_symbols:
            continue
        truth = _numeric_relation(relation)
        if truth is not None:
            decided[relation] = truth
    if not decided:
        return condition
    resolved = condition.xreplace(decided)
    return resolved if isinstance(resolved, Boolean) else condition


def numerically_zero(value: Expr) -> bool:
    if value.is_zero is not None or not value.is_number:
        return value.is_zero is True
    if simplify(value) == 0:
        return True
    try:
        approximate = evaluate_symbolic_precision(value, _NUMERIC_DIGITS)
    except (TypeError, ValueError, ArithmeticError):
        return False
    return approximate.is_zero is True


def reports_undefined(value: SymbolicValue | None) -> bool:
    return isinstance(value, Expr) and (value == nan or value.is_finite is False)


def absorb_undefined(
    operands: Sequence[SymbolicValue],
    result: SymbolicValue,
    point: Mapping[Symbol, Expr] | None = None,
    bound: Symbol | None = None,
) -> SymbolicValue:
    if not isinstance(result, Basic) or _has_undefined(result) or reports_undefined(result):
        return result
    undefined = condition_at(
        Or(
            *(
                undefined_branches(operand)
                for operand in operands
                if isinstance(operand, Basic) and _has_undefined(operand)
            )
        ),
        point or {},
    )
    if undefined == true:
        return nan
    if undefined == false or not isinstance(result, Expr) or bound in undefined.free_symbols:
        return result
    return undefined_when(result, undefined)


def undefined_when(result: Expr, condition: Boolean) -> Expr:
    return piecewise_fold(Piecewise((nan, condition), (result, true)))


def undefined_branches(value: Basic, *, vanishing: bool = False) -> Boolean:
    if isinstance(value, Expr):
        value = piecewise_fold(value)
    if isinstance(value, Piecewise):
        branches: list[Boolean] = []
        reached: Boolean = true
        for branch in value.args:
            met = undefined_branches(branch.expr, vanishing=vanishing)
            branches.append(And(reached, branch.cond, met))
            reached = And(reached, Not(branch.cond))
        return Or(*branches)
    if (
        vanishing
        and isinstance(value, Expr)
        and (numerically_zero(value) or value.is_finite is False)
    ):
        return true
    if not _has_undefined(value):
        return false
    if isinstance(value, Not):
        return Or(*(undefined_branches(argument) for argument in value.args))
    if isinstance(value, And | Or):
        return _undecided_connective(value)
    if not value.args:
        return true
    return Or(*(undefined_branches(argument) for argument in value.args))


def _undecided_connective(value: And | Or) -> Boolean:
    operands = [operand for operand in value.args if isinstance(operand, Boolean)]
    undefined = [undefined_branches(operand) for operand in operands]
    deciding = [Not(operand) if isinstance(value, And) else operand for operand in operands]
    decided = Or(
        *(And(decides, Not(lacks)) for decides, lacks in zip(deciding, undefined, strict=True))
    )
    return And(Or(*undefined), Not(decided))


def _possible_condition(condition: Boolean, point: Substitution) -> Boolean:
    undecided: list[Rel] = []
    for atom in condition.atoms(Rel):
        try:
            substitute_symbols(atom, point)
        except TypeError:
            undecided.append(atom)
    if not undecided or len(undecided) > _MAX_UNDECIDED_RELATIONS:
        return true
    options: list[Boolean] = []
    for choice in itertools.product((true, false), repeat=len(undecided)):
        try:
            resolved = substitute_symbols(
                condition.subs(dict(zip(undecided, choice, strict=True))), point
            )
        except TypeError:
            return true
        options.append(resolved if isinstance(resolved, Boolean) else true)
    return Or(*options)


def _numeric_relation(relation: Rel) -> Boolean | None:
    try:
        difference = relation.lhs - relation.rhs
        real, imaginary = evaluate_symbolic_precision(difference, _NUMERIC_DIGITS).as_real_imag()
    except (TypeError, ValueError, ArithmeticError):
        return None
    if not (real.is_number and imaginary.is_number):
        return None
    if reports_undefined(real) or reports_undefined(imaginary):
        return None
    vanishes = real.is_zero is True and imaginary.is_zero is True
    if relation.rel_op in ("==", "!="):
        return true if vanishes == (relation.rel_op == "==") else false
    if vanishes or imaginary.is_zero is not True:
        return None
    holds = {">": real > 0, ">=": real > 0, "<": real < 0, "<=": real < 0}[relation.rel_op]
    return true if holds else false


def _has_undefined(value: Basic) -> bool:
    return value.has(zoo, nan)
