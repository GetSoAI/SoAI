"""SoAI - Math function catalog shared by numeric and symbolic modes [backend/core/math/function_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import difflib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from core.math.errors import MathExpressionError

__all__ = (
    "MATH_MODE_NUMERIC",
    "MATH_MODE_SYMBOLIC",
    "MATH_MODES",
    "SYMBOLIC_CONSTANT_NAMES",
    "MathFunctionSpec",
    "build_math_function_specs",
    "describe_math_functions",
    "require_math_function_spec",
    "resolve_math_name",
    "validate_math_call_arity",
)

MATH_MODE_NUMERIC = "numeric"
MATH_MODE_SYMBOLIC = "symbolic"
MATH_MODES = (MATH_MODE_NUMERIC, MATH_MODE_SYMBOLIC)
SYMBOLIC_CONSTANT_NAMES = ("pi", "e", "tau", "π", "τ", "I", "oo")
_COMMON_FUNCTION_ALIASES = (
    ("arccos", "acos"),
    ("arcsin", "asin"),
    ("arctan", "atan"),
    ("average", "mean"),
    ("avg", "mean"),
    ("binomial", "comb"),
    ("ceiling", "ceil"),
    ("choose", "comb"),
    ("cuberoot", "cbrt"),
    ("fact", "factorial"),
    ("nCr", "comb"),
    ("nPr", "perm"),
    ("std", "stdev"),
    ("var", "variance"),
)


@dataclass(frozen=True, slots=True)
class MathFunctionSpec:
    name: str
    signature: str
    min_arguments: int
    max_arguments: int | None
    numeric: bool
    symbolic: bool

    @property
    def accepts_value_list(self) -> bool:
        return self.max_arguments is None

    def supports_mode(self, mode: str) -> bool:
        return self.symbolic if mode == MATH_MODE_SYMBOLIC else self.numeric


def _spec(
    signature: str,
    min_arguments: int,
    max_arguments: int | None,
    *,
    numeric: bool = True,
    symbolic: bool = True,
) -> MathFunctionSpec:
    return MathFunctionSpec(
        name=signature.partition("(")[0],
        signature=signature,
        min_arguments=min_arguments,
        max_arguments=max_arguments,
        numeric=numeric,
        symbolic=symbolic,
    )


def build_math_function_specs() -> dict[str, MathFunctionSpec]:
    specs = (
        _spec("abs(x)", 1, 1),
        _spec("sign(x)", 1, 1),
        _spec("round(x[, ndigits])", 1, 2, symbolic=False),
        _spec("floor(x)", 1, 1),
        _spec("ceil(x)", 1, 1),
        _spec("trunc(x)", 1, 1, symbolic=False),
        _spec("sqrt(x)", 1, 1),
        _spec("cbrt(x)", 1, 1),
        _spec("exp(x)", 1, 1),
        _spec("expm1(x)", 1, 1, symbolic=False),
        _spec("log(x[, base])", 1, 2),
        _spec("ln(x)", 1, 1),
        _spec("log10(x)", 1, 1),
        _spec("log2(x)", 1, 1),
        _spec("log1p(x)", 1, 1, symbolic=False),
        _spec("pct(p, x)", 2, 2),
        _spec("clamp(x, low, high)", 3, 3),
        _spec("hypot(x, ...)", 1, None),
        _spec("min(x, ...)", 1, None),
        _spec("max(x, ...)", 1, None),
        _spec("sin(x)", 1, 1),
        _spec("cos(x)", 1, 1),
        _spec("tan(x)", 1, 1),
        _spec("asin(x)", 1, 1),
        _spec("acos(x)", 1, 1),
        _spec("atan(x)", 1, 1),
        _spec("atan2(y, x)", 2, 2),
        _spec("sinh(x)", 1, 1),
        _spec("cosh(x)", 1, 1),
        _spec("tanh(x)", 1, 1),
        _spec("asinh(x)", 1, 1),
        _spec("acosh(x)", 1, 1),
        _spec("atanh(x)", 1, 1),
        _spec("degrees(x)", 1, 1),
        _spec("deg(x)", 1, 1),
        _spec("radians(x)", 1, 1),
        _spec("rad(x)", 1, 1),
        _spec("gamma(x)", 1, 1),
        _spec("lgamma(x)", 1, 1, symbolic=False),
        _spec("erf(x)", 1, 1),
        _spec("erfc(x)", 1, 1),
        _spec("factorial(n)", 1, 1),
        _spec("comb(n, k)", 2, 2),
        _spec("perm(n, k)", 2, 2),
        _spec("gcd(a, ...)", 1, None),
        _spec("lcm(a, ...)", 1, None),
        _spec("isqrt(n)", 1, 1, symbolic=False),
        _spec("sum(x, ...)", 0, None),
        _spec("prod(x, ...)", 0, None),
        _spec("mean(x, ...)", 1, None),
        _spec("median(x, ...)", 1, None, symbolic=False),
        _spec("stdev(x, ...)", 2, None, symbolic=False),
        _spec("pstdev(x, ...)", 1, None, symbolic=False),
        _spec("variance(x, ...)", 2, None, symbolic=False),
        _spec("pvariance(x, ...)", 1, None, symbolic=False),
        _spec("simplify(expr)", 1, 1, numeric=False),
        _spec("expand(expr)", 1, 1, numeric=False),
        _spec("factor(expr)", 1, 1, numeric=False),
        _spec("cancel(expr)", 1, 1, numeric=False),
        _spec("apart(expr[, x])", 1, 2, numeric=False),
        _spec("together(expr)", 1, 1, numeric=False),
        _spec("trigsimp(expr)", 1, 1, numeric=False),
        _spec("solve(equations[, unknowns])", 1, 2, numeric=False),
        _spec("subs(expr, x, value)", 3, 3, numeric=False),
        _spec("N(expr[, digits])", 1, 2, numeric=False),
        _spec("diff(expr, x[, order])", 2, 3, numeric=False),
        _spec("integrate(expr, x[, low, high])", 2, 4, numeric=False),
        _spec("limit(expr, x, point[, side])", 3, 4, numeric=False),
        _spec("series(expr, x[, point, order])", 2, 4, numeric=False),
        _spec("summation(expr, i, low, high)", 4, 4, numeric=False),
        _spec("product(expr, i, low, high)", 4, 4, numeric=False),
        _spec("Matrix(rows)", 1, 1, numeric=False),
        _spec("det(M)", 1, 1, numeric=False),
        _spec("inv(M)", 1, 1, numeric=False),
        _spec("transpose(M)", 1, 1, numeric=False),
        _spec("rank(M)", 1, 1, numeric=False),
        _spec("eigenvals(M)", 1, 1, numeric=False),
    )
    return {spec.name: spec for spec in specs}


def require_math_function_spec(
    name: str,
    *,
    mode: str,
    specs: Mapping[str, MathFunctionSpec],
) -> MathFunctionSpec:
    spec = specs.get(name)
    if spec is None:
        raise MathExpressionError(_unknown_function_message(name, mode=mode, specs=specs))
    if spec.supports_mode(mode):
        return spec
    if mode == MATH_MODE_SYMBOLIC:
        raise MathExpressionError(f"{spec.signature} is only available in mode 'numeric'")
    raise MathExpressionError(f"{spec.signature} requires mode 'symbolic'")


def resolve_math_name[ValueT](
    name: str,
    *,
    variables: Mapping[str, ValueT],
    constants: Mapping[str, ValueT],
    specs: Mapping[str, MathFunctionSpec],
) -> ValueT | None:
    if name in variables:
        return variables[name]
    constant = constants.get(name)
    if constant is not None:
        return constant
    if name in specs:
        raise MathExpressionError(f"'{name}' is a function; call it like {name}(...)")
    return None


def validate_math_call_arity(spec: MathFunctionSpec, argument_count: int) -> None:
    if spec.name == "integrate" and argument_count == 3:
        raise MathExpressionError(
            f"{spec.signature}: provide both the low and high limits, or neither"
        )
    if spec.max_arguments is None:
        if argument_count < spec.min_arguments:
            raise MathExpressionError(
                f"{spec.signature} requires at least {_count_arguments(spec.min_arguments)}, got {argument_count}"
            )
        return
    if spec.min_arguments <= argument_count <= spec.max_arguments:
        return
    if spec.min_arguments == spec.max_arguments:
        expected = _count_arguments(spec.min_arguments)
    else:
        expected = f"{spec.min_arguments} to {spec.max_arguments} arguments"
    raise MathExpressionError(f"{spec.signature} expects {expected}, got {argument_count}")


def describe_math_functions(specs: Iterable[MathFunctionSpec]) -> str:
    return ", ".join(_describe_function(spec) for spec in specs)


def _describe_function(spec: MathFunctionSpec) -> str:
    if spec.max_arguments is None or spec.max_arguments == 1:
        return spec.name
    return spec.signature


def _count_arguments(count: int) -> str:
    return "one argument" if count == 1 else f"{count} arguments"


def _unknown_function_message(
    name: str,
    *,
    mode: str,
    specs: Mapping[str, MathFunctionSpec],
) -> str:
    candidates = [spec.name for spec in specs.values() if spec.supports_mode(mode)]
    suggestions = [
        alias for typo, alias in _COMMON_FUNCTION_ALIASES if typo == name and alias in candidates
    ]
    suggestions.extend(
        match
        for match in difflib.get_close_matches(name, candidates, n=3, cutoff=0.6)
        if match not in suggestions
    )
    if not suggestions:
        return f"Unknown function: {name}"
    return f"Unknown function: {name} (did you mean {' or '.join(suggestions)}?)"
