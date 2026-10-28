"""SoAI - Bounded accuracy requirements for symbolic numerical evaluation [backend/core/math/symbolic_precision.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import overload

from sympy import Expr, ImmutableMatrix, N
from sympy.core.evalf import PrecisionExhausted

from core.math.errors import MathExpressionError
from core.math.expression_limits import MAX_INTEGER_BITS, MAX_RESULT_DIGITS

__all__ = ("evaluate_symbolic_precision",)

_ACCURACY_GUARD_DIGITS = 50


@overload
def evaluate_symbolic_precision(
    value: Expr, digits: int, *, absolute_error: bool = False
) -> Expr: ...


@overload
def evaluate_symbolic_precision(
    value: ImmutableMatrix, digits: int, *, absolute_error: bool = False
) -> ImmutableMatrix: ...


def evaluate_symbolic_precision(
    value: Expr | ImmutableMatrix, digits: int, *, absolute_error: bool = False
) -> Expr | ImmutableMatrix:
    try:
        return N(
            value,
            digits,
            maxn=(
                MAX_RESULT_DIGITS
                + math.ceil(MAX_INTEGER_BITS * math.log10(2))
                + _ACCURACY_GUARD_DIGITS
            ),
            strict=True,
            chop=10.0**-digits if absolute_error else False,
        )
    except (PrecisionExhausted, ValueError) as exception:
        raise MathExpressionError(
            "Numerical evaluation could not reach the required accuracy; simplify the expression or use exact algebra to reduce cancellation"
        ) from exception
