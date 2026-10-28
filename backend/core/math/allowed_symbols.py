"""SoAI - Math allowed symbols [backend/core/math/allowed_symbols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Callable
from fractions import Fraction
from typing import TYPE_CHECKING

from core.math.errors import MathDomainError, MathExpressionError
from core.math.exact_integers import coerce_integral_argument
from core.math.integer_functions import build_integer_functions
from core.math.real_functions import build_real_functions, floating_sign
from core.math.statistics_functions import build_statistics_functions
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from sympy import Expr

    from core.concurrency.deadlines import MonotonicDeadline
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = (
    "CLAMP_BOUNDS_MESSAGE",
    "build_allowed_constants",
    "build_allowed_functions",
    "ensure_logarithm_base",
)

CLAMP_BOUNDS_MESSAGE = "clamp(x, low, high) requires low <= high"
_MAX_FLOAT_ROUNDING_DIGITS = 400


def _safe_abs(value: int | float) -> int | float:
    return abs(value)


def _safe_sign(value: int | float) -> int:
    return int(value > 0) - int(value < 0)


def _safe_round(value: int | float, ndigits: int | float | None = None) -> float | int:
    if ndigits is None:
        return round(value)
    digits = coerce_integral_argument(ndigits, description="ndigits")
    if is_strict_int(value):
        if digits >= 0:
            return value
        if -digits > abs(value).bit_length():
            return 0
        return round(value, digits)
    bounded_digits = max(-_MAX_FLOAT_ROUNDING_DIGITS, min(_MAX_FLOAT_ROUNDING_DIGITS, digits))
    return round(value, bounded_digits)


def _safe_trunc(value: float) -> int:
    return int(math.trunc(value))


def _safe_min(*values: int | float) -> int | float:
    return min(values)


def _safe_max(*values: int | float) -> int | float:
    return max(values)


def ensure_logarithm_base(base: int | float | Expr) -> None:
    for invalid in (0, 1):
        if base == invalid:
            raise MathDomainError(f"the base must not be {invalid}")


def _safe_log(value: float, base: float | None = None) -> float:
    if base is None:
        return math.log(value)
    ensure_logarithm_base(base)
    return math.log(value, base)


def _safe_ln(value: float) -> float:
    return math.log(value)


def _safe_pct(pct: int | float, value: int | float) -> float:
    if pct == 0 or value == 0:
        return math.copysign(0.0, floating_sign(pct) * floating_sign(value))
    return float(Fraction(pct) * Fraction(value) / 100)


def _safe_atan2(ordinate: int | float, abscissa: int | float) -> float:
    if ordinate == 0 and abscissa == 0:
        raise ValueError("the angle is undefined when both arguments are zero")
    if any(is_strict_int(value) and value.bit_length() > 1023 for value in (ordinate, abscissa)):
        scale = max(abs(ordinate), abs(abscissa))
        first = (
            float(Fraction(ordinate) / scale)
            if ordinate
            else math.copysign(0.0, floating_sign(ordinate))
        )
        second = (
            float(Fraction(abscissa) / scale)
            if abscissa
            else math.copysign(0.0, floating_sign(abscissa))
        )
        return math.atan2(first, second)
    return math.atan2(ordinate, abscissa)


def _safe_clamp(value: int | float, low: int | float, high: int | float) -> int | float:
    if low > high:
        raise MathExpressionError(CLAMP_BOUNDS_MESSAGE)
    return max(low, min(high, value))


def build_allowed_functions(
    *,
    deadline: MonotonicDeadline | None = None,
    cancellation_token: CancellationTokenProtocol | None = None,
) -> dict[str, Callable[..., float | int]]:
    return {
        "abs": _safe_abs,
        "sign": _safe_sign,
        "round": _safe_round,
        "floor": math.floor,
        "ceil": math.ceil,
        "trunc": _safe_trunc,
        "atan2": _safe_atan2,
        "log": _safe_log,
        "ln": _safe_ln,
        "log10": math.log10,
        "log2": math.log2,
        "hypot": math.hypot,
        "degrees": math.degrees,
        "deg": math.degrees,
        "min": _safe_min,
        "max": _safe_max,
        "pct": _safe_pct,
        "clamp": _safe_clamp,
        **build_integer_functions(),
        **build_statistics_functions(),
        **build_real_functions(deadline=deadline, cancellation_token=cancellation_token),
    }


def build_allowed_constants() -> dict[str, float]:
    return {"pi": math.pi, "e": math.e, "tau": math.tau, "π": math.pi, "τ": math.tau}
