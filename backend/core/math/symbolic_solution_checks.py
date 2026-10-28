"""SoAI - Validity conditions that make a candidate solution enforceable [backend/core/math/symbolic_solution_checks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import (
    Abs,
    Add,
    Basic,
    Contains,
    Dummy,
    Expr,
    Float,
    Integer,
    Mul,
    Ne,
    Not,
    Poly,
    Rational,
    S,
    cancel,
    default_sort_key,
    expand,
    fraction,
    together,
)
from sympy.logic.boolalg import Boolean

from core.math.symbolic_domain import region_restriction
from core.math.symbolic_operation_domains import record_generated_restrictions
from core.math.symbolic_piecewise_forms import undefined_region
from core.math.symbolic_undefined import reports_undefined
from core.math.symbolic_values import SYMBOLIC_FAILURES, float_precision_bits, require_expression

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sympy import Symbol

    from core.math.symbolic_values import DomainRestriction

__all__ = (
    "as_relations",
    "solution_validity",
)


def solution_validity(
    expression: Expr, point: Mapping[Symbol, Expr], requirement: Boolean = S.true
) -> tuple[DomainRestriction, ...] | None:
    if any(reports_undefined(value) for value in point.values()):
        return None
    restrictions: list[DomainRestriction] = []
    for value in point.values():
        record_generated_restrictions(restrictions, value)
    if len(point) > 1:
        restrictions = [
            region_restriction(undefined_region(restriction)) for restriction in restrictions
        ]
    if requirement != S.true:
        restrictions.append(region_restriction(Not(requirement)))
        return tuple(restrictions)
    substituted = require_expression(expression.subs(point, simultaneous=True), position=1)
    try:
        residual = cancel(substituted)
    except SYMBOLIC_FAILURES:
        residual = substituted
    if reports_undefined(residual):
        return None
    if residual.is_zero is True or _within_rounding_error(expression, point):
        return tuple(restrictions)
    if not residual.free_symbols:
        return None if residual.is_zero is False else tuple(restrictions)
    restrictions.append(region_restriction(Ne(residual, Integer(0))))
    return tuple(restrictions)


def _within_rounding_error(expression: Expr, point: Mapping[Symbol, Expr]) -> bool:
    approximate = expression.atoms(Float) | {
        number for value in point.values() for number in value.atoms(Float)
    }
    if not approximate or not expression.is_polynomial(*point):
        return False
    exact: dict[Basic, Basic] = {number: Rational(number) for number in approximate}
    exact_point = {
        symbol: require_expression(value.xreplace(exact), position=1)
        for symbol, value in point.items()
    }
    expanded = expand(require_expression(expression.xreplace(exact), position=1))
    terms = expanded.args if isinstance(expanded, Add) else (expanded,)
    substituted = [
        together(require_expression(term.subs(exact_point, simultaneous=True), position=1))
        for term in terms
    ]
    parameters = sorted(
        {symbol for term in substituted for symbol in term.free_symbols}, key=default_sort_key
    )
    denominator = Mul(*{fraction(term)[1] for term in substituted})
    coefficients: dict[Expr, list[Expr]] = {}
    for term in substituted:
        expanded = expand(term * denominator)
        for component in expanded.args if isinstance(expanded, Add) else (expanded,):
            coefficient, monomial = require_expression(component, position=1).as_independent(
                *parameters, as_Add=False
            )
            if coefficient.is_finite is not True:
                return False
            if monomial not in coefficients:
                coefficients[monomial] = []
            coefficients[monomial].append(coefficient)
    precision = min(float_precision_bits(number) for number in approximate)
    operations = 2 * Poly(expression, *(point or (Dummy("constant"),))).total_degree() + len(terms)
    relative_error = operations * Rational(1, 2) ** (precision - 1)
    if relative_error >= 1:
        raise ValueError(
            "the numerical solution cannot be verified at its carried precision; use exact coefficients or increase the precision with N(expr, digits)"
        )
    tolerance = relative_error / (1 - relative_error)
    return all(
        (
            _coefficient_norm(Add(*values))
            <= tolerance * Add(*(_coefficient_norm(value) for value in values))
        )
        == S.true
        for values in coefficients.values()
    )


def _coefficient_norm(value: Expr) -> Expr:
    return Add(
        *(
            Rational(abs(part.p), part.q) if isinstance(part, Rational) else Abs(part)
            for part in value.as_real_imag()
        )
    )


def as_relations(condition: Boolean) -> Boolean:
    if not isinstance(condition, Contains):
        return condition
    element, values = condition.args
    probe = Dummy("value", real=True)
    relations = values.as_relational(probe).xreplace({probe: element})
    return relations if isinstance(relations, Boolean) else condition
