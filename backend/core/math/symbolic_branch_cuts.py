"""SoAI - Real-coordinate crossings of principal complex branches [backend/core/math/symbolic_branch_cuts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import (
    Dummy,
    Expr,
    Ge,
    Integer,
    Le,
    Lt,
    Pow,
    acos,
    acosh,
    asin,
    asinh,
    atan,
    atan2,
    atanh,
    default_sort_key,
    false,
    log,
    true,
)
from sympy.logic.boolalg import Boolean

from core.math.symbolic_piecewise_forms import polynomial_roots
from core.math.symbolic_undefined import condition_at
from core.math.symbolic_values import require_expression

if TYPE_CHECKING:
    from sympy import Symbol

__all__ = ("branch_cut_points",)

_MAX_CROSSINGS = 16
_UNCHECKED_MESSAGE = "the expression could not be checked across its complex branch cuts; substitute values for the parameters or rewrite it; for integration, split the path into intervals that avoid the cuts"


def branch_cut_points(expression: Expr, symbol: Symbol) -> tuple[Expr, ...]:
    coordinate: Symbol = Dummy(symbol.name, real=True)
    probed = expression.subs(symbol, coordinate)
    branches: list[Expr] = list(probed.atoms(log, asin, acos, atan, atan2, asinh, acosh, atanh))
    branches.extend(power for power in probed.atoms(Pow) if power.exp.is_integer is not True)
    points: set[Expr] = set()
    for branch in branches:
        argument = require_expression(branch.args[0], position=1)
        if coordinate not in argument.free_symbols:
            continue
        real, imaginary = argument.as_real_imag()
        reached = _cut_region(branch, real, imaginary)
        if reached == false:
            continue
        normal = (
            argument
            if isinstance(branch, atan2)
            else real if isinstance(branch, atan | asinh) else imaginary
        )
        if coordinate not in normal.free_symbols or normal.is_zero is False:
            continue
        if not normal.is_polynomial(coordinate):
            raise ValueError(_UNCHECKED_MESSAGE)
        roots = polynomial_roots(normal, coordinate)
        if roots is None:
            raise ValueError(_UNCHECKED_MESSAGE)
        points.update(
            point for point in roots if condition_at(reached, {coordinate: point}) != false
        )
        if len(points) > _MAX_CROSSINGS:
            raise ValueError(_UNCHECKED_MESSAGE)
    return tuple(sorted(points, key=default_sort_key))


def _cut_region(branch: Expr, real: Expr, imaginary: Expr) -> Boolean:
    if isinstance(branch, atan2):
        abscissa = require_expression(branch.args[1], position=2)
        return Lt(abscissa, Integer(0)) if abscissa.is_extended_real is True else true
    if isinstance(branch, atan | asinh):
        return Ge(imaginary**2, Integer(1))
    if isinstance(branch, log | Pow):
        return Le(real, Integer(0))
    if isinstance(branch, acosh):
        return Le(real, Integer(1))
    return Ge(real**2, Integer(1))
