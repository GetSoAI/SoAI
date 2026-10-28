"""SoAI - Poles that a definite integral crosses for some parameter values [backend/core/math/symbolic_poles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import Abs, Dummy, Expr, Integer, Ne, atan, atanh, false, fraction, limit, log, together
from sympy.logic.boolalg import And, Boolean, Or

from core.math.symbolic_domain import region_condition
from core.math.symbolic_piecewise_forms import polynomial_roots, real_piecewise
from core.math.symbolic_spans import infinite_axis, span_contains
from core.math.symbolic_undefined import condition_at
from core.math.symbolic_values import SYMBOLIC_FAILURES, require_expression
from core.math.symbolic_vanishing import zero_factors

if TYPE_CHECKING:
    from sympy import Symbol

    from core.math.symbolic_values import DomainRestriction

__all__ = ("crossed_poles",)

_UNLOCATED_POLE_MESSAGE = "the integral may cross a point where the integrand is undefined, at a position that depends on the parameters; substitute values for the parameters first"
_UNDECIDED_CONVERGENCE_MESSAGE = "convergence at a parameter-dependent singularity could not be determined; substitute values for the parameters or split the interval at the singularity"


def crossed_poles(
    restriction: DomainRestriction, symbol: Symbol, integrand: Expr, low: Expr, high: Expr
) -> Boolean:
    zero = restriction.zero
    nonempty = Ne(low, high)
    if (
        nonempty == false
        or region_condition(zero) is not None
        or not ((zero.free_symbols | low.free_symbols | high.free_symbols) - {symbol})
    ):
        return false
    numerator, _denominator = fraction(together(zero))
    roots: list[Expr] = []
    for factor in zero_factors(numerator):
        if symbol not in factor.free_symbols:
            continue
        found = (
            polynomial_roots(factor, symbol, real_only=False)
            if factor.is_polynomial(symbol)
            else None
        )
        if found is None:
            raise ValueError(_UNLOCATED_POLE_MESSAGE)
        roots.extend(found)
    direction = high - low
    axis = infinite_axis(low, high)
    if axis is not None:
        direction = axis
    elif direction.is_extended_real is True:
        direction = Integer(1)
    elif not direction.is_number:
        direction = Dummy("direction", finite=True, zero=False)
    crossings: list[Boolean] = []
    for point in roots:
        reached = And(
            condition_at(restriction.condition, {symbol: point}),
            span_contains(point, low, high),
        )
        if reached == false or _integrable(integrand, symbol, point, direction):
            continue
        crossings.append(reached)
    return Or(*crossings)


def _integrable(function: Expr, symbol: Symbol, point: Expr, direction: Expr) -> bool:
    step = Dummy("step", positive=True)
    convergent: list[bool] = []
    try:
        function = require_expression(
            function.xreplace(
                {inverse: inverse.rewrite(log) for inverse in function.atoms(atan, atanh)}
            ),
            position=1,
        )
        for side in (1, -1):
            shifted = require_expression(
                function.subs(symbol, point + side * direction * step), position=1
            )
            shifted = real_piecewise(shifted, step)
            magnitude = Abs(shifted)
            if limit(magnitude, step, Integer(0), "+").is_finite is True:
                convergent.append(True)
                continue
            order = limit(log(magnitude) / log(step), step, Integer(0), "+")
            if (order + 1).is_extended_positive is True or shifted == 0:
                convergent.append(True)
            elif (order + 1).is_extended_negative is True or order == -1:
                if (order + 1).is_extended_negative is True and shifted.free_symbols <= {step}:
                    phase = limit(shifted / magnitude, step, Integer(0), "+")
                    if phase.is_finite is True and phase.is_zero is False:
                        convergent.append(False)
                        continue
                leading = limit(step ** (-order) * shifted, step, Integer(0), "+")
                if leading.is_finite is True and leading.is_zero is False:
                    convergent.append(False)
                elif order == -1:
                    logarithmic_order = limit(
                        log(step * Abs(shifted)) / log(-log(step)), step, Integer(0), "+"
                    )
                    if (logarithmic_order + 1).is_extended_negative is True:
                        convergent.append(True)
                    else:
                        raise ValueError(_UNDECIDED_CONVERGENCE_MESSAGE)
                else:
                    raise ValueError(_UNDECIDED_CONVERGENCE_MESSAGE)
            else:
                raise ValueError(_UNDECIDED_CONVERGENCE_MESSAGE)
    except SYMBOLIC_FAILURES as exception:
        raise ValueError(_UNDECIDED_CONVERGENCE_MESSAGE) from exception
    return all(convergent)
