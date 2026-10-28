"""SoAI - Real functions with exact large-integer operands [backend/core/math/real_functions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from decimal import Decimal, Overflow, localcontext
from fractions import Fraction
from functools import partial
from typing import TYPE_CHECKING

from core.math.errors import MathExpressionError
from core.math.symbolic_process import SYMBOLIC_WORKER_MODULE, read_symbolic_worker_result
from core.math.symbolic_requests import build_symbolic_worker_request
from core.meta.paths import get_backend_root
from core.system.commands import run_argv_capture
from core.timing.constants import CONTROL_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.concurrency.deadlines import MonotonicDeadline
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = ("build_real_functions", "floating_sign", "real_power")

_FLOAT_MAX_EXPONENT = 1023
_DECIMAL_DIGITS = 80


def floating_sign(value: int | float) -> float:
    return math.copysign(1.0, value) if isinstance(value, float) else (-1.0 if value < 0 else 1.0)


def build_real_functions(
    *,
    deadline: MonotonicDeadline | None = None,
    cancellation_token: CancellationTokenProtocol | None = None,
) -> dict[str, Callable[..., float]]:
    functions: dict[str, Callable[[int | float], float]] = {
        "sqrt": math.sqrt,
        "cbrt": math.cbrt,
        "exp": math.exp,
        "expm1": math.expm1,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "sinh": math.sinh,
        "cosh": math.cosh,
        "tanh": math.tanh,
        "asinh": math.asinh,
        "acosh": math.acosh,
        "atanh": math.atanh,
        "log1p": math.log1p,
        "gamma": math.gamma,
        "lgamma": math.lgamma,
        "erf": math.erf,
        "erfc": math.erfc,
        "radians": math.radians,
    }
    real_functions: dict[str, Callable[..., float]] = {
        name: partial(
            _real_call,
            name=name,
            function=function,
            deadline=deadline,
            cancellation_token=cancellation_token,
        )
        for name, function in functions.items()
    }
    real_functions["rad"] = real_functions["radians"]
    return real_functions


def _real_call(
    value: int | float,
    *,
    name: str,
    function: Callable[[int | float], float],
    deadline: MonotonicDeadline | None,
    cancellation_token: CancellationTokenProtocol | None,
) -> float:
    if isinstance(value, int) and value.bit_length() > 53 and name in ("sin", "cos", "tan"):
        return _integer_trigonometric(
            value, name, deadline=deadline, cancellation_token=cancellation_token
        )
    if not isinstance(value, int) or value.bit_length() <= _FLOAT_MAX_EXPONENT:
        return function(value)
    if name in ("sqrt", "cbrt"):
        if value < 0 and name == "sqrt":
            raise ValueError("math domain error")
        with localcontext() as context:
            context.prec = _DECIMAL_DIGITS
            magnitude = Decimal(abs(value))
            root = magnitude.sqrt() if name == "sqrt" else context.power(magnitude, Decimal(1) / 3)
        return float(root) * (floating_sign(value) if name == "cbrt" else 1)
    if name in ("asin", "acos", "atanh") or (
        value < 0 and name in ("acosh", "log1p", "gamma", "lgamma")
    ):
        raise ValueError("math domain error")
    if name == "atan":
        return floating_sign(value) * math.pi / 2
    if name == "asinh":
        return floating_sign(value) * (math.log(abs(value)) + math.log(2))
    if name == "acosh" and value > 0:
        return math.log(value) + math.log(2)
    if name == "log1p" and value > 0:
        return math.log(value)
    if name in ("exp", "expm1") and value < 0:
        return 0.0 if name == "exp" else -1.0
    if name in ("tanh", "erf"):
        return floating_sign(value)
    if name == "erfc":
        return 0.0 if value > 0 else 2.0
    if name == "radians":
        return float(Fraction(value) * Fraction(math.pi) / 180)
    return function(value)


def _integer_trigonometric(
    value: int,
    name: str,
    *,
    deadline: MonotonicDeadline | None,
    cancellation_token: CancellationTokenProtocol | None,
) -> float:
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
    timeout_sec = CONTROL_TIMEOUT_SEC if deadline is None else deadline.remaining_seconds()
    if timeout_sec <= 0:
        raise TimeoutError("Numeric evaluation deadline expired")
    request = build_symbolic_worker_request(
        f"N({name}({hex(value)}),25)", None, timeout_sec=timeout_sec
    )
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
    if deadline is not None:
        timeout_sec = deadline.remaining_seconds()
        if timeout_sec <= 0:
            raise TimeoutError("Numeric evaluation deadline expired")
    captured = run_argv_capture(
        [sys.executable, "-m", SYMBOLIC_WORKER_MODULE],
        timeout=timeout_sec,
        stdin_text=request,
        cwd=get_backend_root(),
    )
    if deadline is not None and (captured.timed_out or deadline.expired()):
        raise TimeoutError("Numeric evaluation deadline expired")
    projection = read_symbolic_worker_result(captured, timeout_sec=timeout_sec)
    result = projection.get("result")
    if not isinstance(result, int | float) or isinstance(result, bool):
        raise MathExpressionError(
            "The trigonometric result could not be evaluated as a finite real number"
        )
    text = projection.get("result_text")
    if not isinstance(text, str):
        raise MathExpressionError("The trigonometric result has no decimal representation")
    return float(text)


def real_power(base: int | float, exponent: int | float) -> float:
    if (isinstance(base, int) and base.bit_length() > _FLOAT_MAX_EXPONENT) or (
        isinstance(exponent, int) and exponent.bit_length() > 53
    ):
        try:
            with localcontext() as context:
                context.prec = _DECIMAL_DIGITS
                return float(context.power(Decimal(base), Decimal(exponent)))
        except Overflow as exception:
            raise OverflowError("power exceeds the floating-point range") from exception
    return math.pow(base, exponent)
