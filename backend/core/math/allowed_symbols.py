"""SoAI - Math allowed symbols [backend/core/math/allowed_symbols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Callable

from core.math.errors import MathExpressionError
from core.validation.integers import is_strict_int

__all__ = (
    "build_allowed_constants",
    "build_allowed_functions",
)


def _safe_abs(value: float) -> float | int:
    return abs(value)


def _safe_round(value: int | float, ndigits: int | None = None) -> float | int:
    if ndigits is None:
        return round(value)
    if (
        is_strict_int(value)
        and is_strict_int(ndigits)
        and ndigits < 0
        and -ndigits > abs(value).bit_length()
    ):
        return 0
    return round(value, ndigits)


def _safe_trunc(value: float) -> int:
    return int(math.trunc(value))


def _safe_min(*values: float) -> float | int:
    if not values:
        raise MathExpressionError("min(...) requires at least one argument")
    return min(values)


def _safe_max(*values: float) -> float | int:
    if not values:
        raise MathExpressionError("max(...) requires at least one argument")
    return max(values)


def _safe_log(value: float, base: float | None = None) -> float:
    return math.log(value) if base is None else math.log(value, base)


def _safe_ln(value: float) -> float:
    return math.log(value)


def _safe_pct(pct: float, value: float) -> float:
    return (pct / 100.0) * value


def _safe_clamp(value: float, low: float, high: float) -> float:
    if low > high:
        raise MathExpressionError("clamp(x, low, high) requires low <= high")
    return max(low, min(high, value))


def build_allowed_functions() -> dict[str, Callable[..., float | int]]:
    return {
        "abs": _safe_abs,
        "round": _safe_round,
        "floor": math.floor,
        "ceil": math.ceil,
        "trunc": _safe_trunc,
        "sqrt": math.sqrt,
        "exp": math.exp,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "atan2": math.atan2,
        "sinh": math.sinh,
        "cosh": math.cosh,
        "tanh": math.tanh,
        "log": _safe_log,
        "ln": _safe_ln,
        "log10": math.log10,
        "log2": math.log2,
        "hypot": math.hypot,
        "degrees": math.degrees,
        "deg": math.degrees,
        "radians": math.radians,
        "rad": math.radians,
        "min": _safe_min,
        "max": _safe_max,
        "pct": _safe_pct,
        "clamp": _safe_clamp,
    }


def build_allowed_constants() -> dict[str, float]:
    return {"pi": math.pi, "e": math.e, "tau": math.tau}
