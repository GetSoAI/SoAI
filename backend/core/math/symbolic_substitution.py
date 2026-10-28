"""SoAI - Capture-free symbolic substitution and deferred integral completion [backend/core/math/symbolic_substitution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import Basic, Dummy, Expr, Integer, Integral, Order

from core.math.symbolic_bindings import prepare_substitution, substitute_symbols
from core.math.symbolic_integral_checks import has_unresolved_branch_parameters, integral_branches
from core.math.symbolic_piecewise_forms import is_analytic, real_piecewise
from core.math.symbolic_spans import integral_path
from core.math.symbolic_values import require_expression, require_single_value, require_symbol

if TYPE_CHECKING:
    from collections.abc import Callable

    from sympy import Symbol

    from core.math.symbolic_values import SymbolicValue

    type IntegralEvaluator = Callable[[Expr, Symbol, Expr | None, Expr | None], Expr]

__all__ = ("complete_integral", "substitute_value")


def substitute_value(
    value: SymbolicValue,
    variable: SymbolicValue,
    replacement: SymbolicValue,
    *,
    evaluate_integral: IntegralEvaluator,
) -> Basic:
    target = require_single_value(value, position=1)
    symbol = require_symbol(variable, position=2)
    point = require_expression(replacement, position=3)
    target = prepare_substitution(target, symbol, point)
    result = target.subs(symbol, point)
    result = result.xreplace(
        {remainder: Integer(0) for remainder in result.atoms(Order) if remainder.expr == 0}
    )
    for pending in sorted(
        target.atoms(Integral), key=lambda integral: len(integral.atoms(Integral)), reverse=True
    ):
        if symbol not in pending.free_symbols:
            continue
        if not pending.function.has(Integral) and all(
            is_analytic(pending.function, boundary[0])
            and not integral_branches(pending.function, boundary[0])
            for boundary in pending.limits
        ):
            continue
        concrete = pending.subs(symbol, point)
        if isinstance(concrete, Integral) and concrete in result.atoms(Integral):
            result = result.xreplace({concrete: complete_integral(concrete, evaluate_integral)})
    return result


def _can_complete(integral: Integral, context: frozenset[Symbol]) -> bool:
    coordinates = {boundary[0] for boundary in integral.limits}
    parameters = integral.function.free_symbols - coordinates - context
    return not any(
        has_unresolved_branch_parameters(integral.function, coordinate, parameters=parameters)
        for coordinate in coordinates
    ) and not any(
        endpoint.free_symbols - {outer[0] for outer in integral.limits[index + 1 :]} - context
        for index, boundary in enumerate(integral.limits)
        if len(boundary) == 3
        for endpoint in boundary[1:]
    )


def complete_integral(
    integral: Integral,
    evaluate_integral: IntegralEvaluator,
    *,
    context: frozenset[Symbol] = frozenset(),
) -> Expr:
    if not _can_complete(integral, context):
        return integral
    prepared = _real_coordinates(integral)
    if not isinstance(prepared, Integral):
        return prepared
    result = prepared.function
    context = context | frozenset(
        boundary[0] for boundary in prepared.limits if boundary[0].is_real is True
    )
    for nested in sorted(
        result.atoms(Integral), key=lambda value: len(value.atoms(Integral)), reverse=True
    ):
        result = require_expression(
            result.xreplace(
                {nested: complete_integral(nested, evaluate_integral, context=context)}
            ),
            position=1,
        )
    if result.has(Integral):
        return integral
    for boundary in prepared.limits:
        result = real_piecewise(result, boundary[0])
    for boundary in prepared.limits:
        coordinate = boundary[0]
        if len(boundary) == 3:
            result = evaluate_integral(result, coordinate, boundary[1], boundary[2])
        else:
            result = evaluate_integral(result, coordinate, None, None)
            if len(boundary) == 2 and not result.has(Integral):
                result = require_expression(
                    substitute_symbols(result, {coordinate: boundary[1]}), position=1
                )
        if result.has(Integral):
            return integral
    return result


def _real_coordinates(integral: Integral) -> Expr:
    prepared = integral
    for index in reversed(range(len(prepared.limits))):
        boundary = prepared.limits[index]
        coordinate = boundary[0]
        offset: Expr = Integer(0)
        scale: Expr = Integer(1)
        parameter_assumptions: dict[str, bool] = {"real": True}
        replacement: tuple[Symbol, Expr] | tuple[Symbol, Expr, Expr]
        if len(boundary) == 3:
            low, high = boundary[1:]
            if low == high:
                return Integer(0)
            path = integral_path(low, high)
            if path is None:
                if not all(endpoint.is_extended_real is True for endpoint in (low, high)):
                    return integral
                path = (Integer(0), Integer(1), low, high)
            offset, scale, first, last = path
            if all(endpoint.is_nonnegative is True for endpoint in (first, last)):
                parameter_assumptions["nonnegative"] = True
            elif all((-endpoint).is_nonnegative is True for endpoint in (first, last)):
                parameter_assumptions["nonpositive"] = True
            parameter = Dummy(coordinate.name, **parameter_assumptions)
            replacement = (parameter, first, last)
        else:
            parameter = Dummy(coordinate.name, **parameter_assumptions)
            replacement = (parameter, boundary[1] if len(boundary) == 2 else coordinate)
        point = {coordinate: offset + scale * parameter}
        preceding = prepared.limits[:index]
        function = prepared.function
        if preceding:
            nested = substitute_symbols(Integral(function, *preceding), point)
            if not isinstance(nested, Integral):
                return require_expression(nested, position=1)
            function, preceding = nested.function, nested.limits
        else:
            function = require_expression(substitute_symbols(function, point), position=1)
        prepared = Integral(
            scale * function,
            *preceding,
            replacement,
            *prepared.limits[index + 1 :],
        )
    return prepared
