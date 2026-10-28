"""SoAI - Symbolic adapters for functions shared with numeric mode [backend/core/math/symbolic_functions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

from sympy import (
    Abs,
    Add,
    Expr,
    Integer,
    Le,
    Max,
    Min,
    Mul,
    acos,
    acosh,
    asin,
    asinh,
    atan,
    atan2,
    atanh,
    binomial,
    ceiling,
    cos,
    cosh,
    erf,
    erfc,
    exp,
    factorial,
    false,
    ff,
    floor,
    gamma,
    log,
    pi,
    real_root,
    sign,
    sin,
    sinh,
    sqrt,
    tan,
    tanh,
)

from core.math.allowed_symbols import CLAMP_BOUNDS_MESSAGE, ensure_logarithm_base
from core.math.errors import MathDomainError
from core.math.exact_integers import (
    coerce_non_negative_integral_argument,
    ensure_binomial_within_budget,
    ensure_factorial_within_budget,
    ensure_permutation_within_budget,
    exact_least_common_multiple,
)
from core.math.symbolic_operations import build_symbolic_operations
from core.math.symbolic_values import require_expression, require_expressions

if TYPE_CHECKING:
    from collections.abc import Sequence

    from core.math.symbolic_values import SymbolicValue

__all__ = ("build_symbolic_functions",)

_INTEGER_SYMBOLS_MESSAGE = "this function works on integers; substitute integer values for the symbols first, or use factor and cancel for polynomials"


def build_symbolic_functions() -> dict[str, Callable[..., SymbolicValue]]:
    unary_functions: dict[str, Callable[[Expr], Expr]] = {
        "abs": Abs,
        "sign": sign,
        "floor": floor,
        "ceil": ceiling,
        "sqrt": sqrt,
        "exp": exp,
        "ln": log,
        "sin": sin,
        "cos": cos,
        "tan": tan,
        "asin": asin,
        "acos": acos,
        "atan": atan,
        "sinh": sinh,
        "cosh": cosh,
        "tanh": tanh,
        "asinh": asinh,
        "acosh": acosh,
        "atanh": atanh,
        "gamma": gamma,
        "erf": erf,
        "erfc": erfc,
    }
    functions: dict[str, Callable[..., SymbolicValue]] = {
        name: partial(_apply_unary, function=function) for name, function in unary_functions.items()
    }
    functions.update(
        {
            "cbrt": _cube_root,
            "log": _logarithm,
            "log10": partial(_logarithm, base=Integer(10)),
            "log2": partial(_logarithm, base=Integer(2)),
            "pct": _percentage,
            "clamp": _clamp,
            "hypot": _hypotenuse,
            "min": _minimum,
            "max": _maximum,
            "atan2": _two_argument_arctangent,
            "degrees": partial(_scale, factor=180 / pi),
            "deg": partial(_scale, factor=180 / pi),
            "radians": partial(_scale, factor=pi / 180),
            "rad": partial(_scale, factor=pi / 180),
            "factorial": _factorial,
            "comb": _combinations,
            "perm": _permutations,
            "gcd": _greatest_common_divisor,
            "lcm": _least_common_multiple,
            "sum": _sum,
            "prod": _product,
            "mean": _mean,
        }
    )
    functions.update(build_symbolic_operations())
    return functions


def _apply_unary(value: SymbolicValue, *, function: Callable[[Expr], Expr]) -> Expr:
    return function(require_expression(value, position=1))


def _cube_root(value: SymbolicValue) -> Expr:
    return real_root(require_expression(value, position=1), 3)


def _logarithm(value: SymbolicValue, base: SymbolicValue | None = None) -> Expr:
    argument = require_expression(value, position=1)
    if base is None:
        return log(argument)
    resolved_base = require_expression(base, position=2)
    ensure_logarithm_base(resolved_base)
    return log(argument, resolved_base)


def _percentage(percent: SymbolicValue, value: SymbolicValue) -> Expr:
    return require_expression(percent, position=1) / 100 * require_expression(value, position=2)


def _clamp(value: SymbolicValue, low: SymbolicValue, high: SymbolicValue) -> Expr:
    low_bound = require_expression(low, position=2)
    high_bound = require_expression(high, position=3)
    if Le(low_bound, high_bound) == false or (high_bound - low_bound).is_negative is True:
        raise MathDomainError(CLAMP_BOUNDS_MESSAGE)
    return Min(Max(require_expression(value, position=1), low_bound), high_bound)


def _hypotenuse(*values: SymbolicValue) -> Expr:
    return sqrt(Add(*(value**2 for value in require_expressions(values))))


def _minimum(*values: SymbolicValue) -> Expr:
    return Min(*require_expressions(values))


def _maximum(*values: SymbolicValue) -> Expr:
    return Max(*require_expressions(values))


def _two_argument_arctangent(ordinate: SymbolicValue, abscissa: SymbolicValue) -> Expr:
    return atan2(require_expression(ordinate, position=1), require_expression(abscissa, position=2))


def _scale(value: SymbolicValue, *, factor: Expr) -> Expr:
    return require_expression(value, position=1) * factor


def _exact_count(value: Expr, *, description: str) -> int | None:
    if isinstance(value, Integer):
        try:
            return coerce_non_negative_integral_argument(int(value), description=description)
        except ValueError as exception:
            raise MathDomainError(str(exception)) from exception
    return None


def _factorial(value: SymbolicValue) -> Expr:
    argument = require_expression(value, position=1)
    count = _exact_count(argument, description="n")
    if count is not None:
        ensure_factorial_within_budget(count)
    return factorial(argument)


def _combinations(total: SymbolicValue, chosen: SymbolicValue) -> Expr:
    total_expression = require_expression(total, position=1)
    chosen_expression = require_expression(chosen, position=2)
    exact_total = _exact_count(total_expression, description="n")
    exact_chosen = _exact_count(chosen_expression, description="k")
    if exact_total is not None and exact_chosen is not None:
        ensure_binomial_within_budget(exact_total, exact_chosen)
    return binomial(total_expression, chosen_expression)


def _permutations(total: SymbolicValue, chosen: SymbolicValue) -> Expr:
    total_expression = require_expression(total, position=1)
    chosen_expression = require_expression(chosen, position=2)
    exact_total = _exact_count(total_expression, description="n")
    exact_chosen = _exact_count(chosen_expression, description="k")
    if exact_total is not None and exact_chosen is not None:
        ensure_permutation_within_budget(exact_total, exact_chosen)
    return ff(total_expression, chosen_expression)


def _greatest_common_divisor(*values: SymbolicValue) -> Expr:
    return Integer(math.gcd(*_integer_arguments(values)))


def _least_common_multiple(*values: SymbolicValue) -> Expr:
    return Integer(exact_least_common_multiple(_integer_arguments(values)))


def _integer_arguments(values: Sequence[SymbolicValue]) -> list[int]:
    integers: list[int] = []
    for position, expression in enumerate(require_expressions(values), 1):
        if not isinstance(expression, Integer):
            raise ValueError(
                _INTEGER_SYMBOLS_MESSAGE
                if expression.free_symbols
                else f"argument {position} must be an integer"
            )
        integers.append(int(expression))
    return integers


def _sum(*values: SymbolicValue) -> Expr:
    return Add(*require_expressions(values))


def _product(*values: SymbolicValue) -> Expr:
    return Mul(*require_expressions(values))


def _mean(*values: SymbolicValue) -> Expr:
    expressions = require_expressions(values)
    return Add(*expressions) / len(expressions)
