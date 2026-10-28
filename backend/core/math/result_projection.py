"""SoAI - JSON projection of math evaluation results [backend/core/math/result_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from core.math.errors import MathExpressionError
from core.math.expression_limits import DISPLAY_SIGNIFICANT_DIGITS, MAX_RESULT_DIGITS
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.math.program_evaluation import MathEvaluation, MathValue
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "MATH_OUTCOMES",
    "OUTCOME_ALL_VALUES",
    "OUTCOME_BOUNDED_OSCILLATION",
    "OUTCOME_COMPLEX_INFINITY",
    "OUTCOME_CONDITIONAL",
    "OUTCOME_INFINITE",
    "OUTCOME_INFINITELY_MANY",
    "OUTCOME_NO_LIMIT",
    "OUTCOME_NO_SOLUTION",
    "OUTCOME_PARTIAL_SOLUTIONS",
    "OUTCOME_SOLUTIONS",
    "OUTCOME_UNDEFINED",
    "OUTCOME_UNDETERMINED",
    "OUTCOME_UNEVALUATED",
    "RESULT_TYPES",
    "RESULT_TYPE_BOOLEAN",
    "RESULT_TYPE_COMPLEX",
    "RESULT_TYPE_EXPRESSION",
    "RESULT_TYPE_INTEGER",
    "RESULT_TYPE_LIST",
    "RESULT_TYPE_MATRIX",
    "RESULT_TYPE_INFINITY",
    "RESULT_TYPE_RATIONAL",
    "RESULT_TYPE_REAL",
    "RESULT_TYPE_SOLUTION",
    "RESULT_TYPE_SOLUTIONS",
    "RESULT_TYPE_UNDEFINED",
    "describe_result_target",
    "ensure_displayable_integer",
    "format_real_number",
    "project_integer",
    "project_math_evaluation",
    "project_math_value",
)

RESULT_TYPE_INTEGER = "integer"
RESULT_TYPE_REAL = "real"
RESULT_TYPE_BOOLEAN = "boolean"
RESULT_TYPE_RATIONAL = "rational"
RESULT_TYPE_COMPLEX = "complex"
RESULT_TYPE_EXPRESSION = "expression"
RESULT_TYPE_LIST = "list"
RESULT_TYPE_MATRIX = "matrix"
RESULT_TYPE_SOLUTIONS = "solutions"
RESULT_TYPE_SOLUTION = "solution"
RESULT_TYPE_INFINITY = "infinity"
RESULT_TYPE_UNDEFINED = "undefined"
RESULT_TYPES = (
    RESULT_TYPE_INTEGER,
    RESULT_TYPE_REAL,
    RESULT_TYPE_BOOLEAN,
    RESULT_TYPE_RATIONAL,
    RESULT_TYPE_COMPLEX,
    RESULT_TYPE_EXPRESSION,
    RESULT_TYPE_LIST,
    RESULT_TYPE_MATRIX,
    RESULT_TYPE_SOLUTIONS,
    RESULT_TYPE_SOLUTION,
    RESULT_TYPE_INFINITY,
    RESULT_TYPE_UNDEFINED,
)
OUTCOME_SOLUTIONS = "solutions"
OUTCOME_NO_SOLUTION = "no_solution"
OUTCOME_ALL_VALUES = "all_values"
OUTCOME_INFINITELY_MANY = "infinitely_many"
OUTCOME_PARTIAL_SOLUTIONS = "partial_solutions"
OUTCOME_UNDETERMINED = "undetermined"
OUTCOME_CONDITIONAL = "conditional"
OUTCOME_INFINITE = "infinite"
OUTCOME_COMPLEX_INFINITY = "complex_infinity"
OUTCOME_UNDEFINED = "undefined"
OUTCOME_NO_LIMIT = "no_limit"
OUTCOME_BOUNDED_OSCILLATION = "bounded_oscillation"
OUTCOME_UNEVALUATED = "unevaluated"
MATH_OUTCOMES = (
    OUTCOME_SOLUTIONS,
    OUTCOME_NO_SOLUTION,
    OUTCOME_ALL_VALUES,
    OUTCOME_INFINITELY_MANY,
    OUTCOME_PARTIAL_SOLUTIONS,
    OUTCOME_UNDETERMINED,
    OUTCOME_CONDITIONAL,
    OUTCOME_INFINITE,
    OUTCOME_COMPLEX_INFINITY,
    OUTCOME_UNDEFINED,
    OUTCOME_NO_LIMIT,
    OUTCOME_BOUNDED_OSCILLATION,
    OUTCOME_UNEVALUATED,
)
_MAX_SAFE_JSON_INTEGER = 9007199254740992


def format_real_number(value: float) -> str:
    return format(value, f".{DISPLAY_SIGNIFICANT_DIGITS}g")


def describe_result_target(name: str | None) -> str:
    return "Result" if name is None else f"Value of '{name}'"


def ensure_displayable_integer(value: int, *, name: str | None) -> str:
    if abs(value) >= 10**MAX_RESULT_DIGITS:
        raise MathExpressionError(
            f"{describe_result_target(name)} is too large to display: integers are shown exactly up to {MAX_RESULT_DIGITS} digits"
        )
    return str(value)


def project_integer(value: int, name: str | None = None) -> JSONDict:
    text = ensure_displayable_integer(value, name=name)
    projection: JSONDict = {"result_text": text, "result_type": RESULT_TYPE_INTEGER, "exact": True}
    if abs(value) <= _MAX_SAFE_JSON_INTEGER:
        projection["result"] = value
        return projection
    try:
        approximation = float(value)
    except OverflowError:
        return projection
    projection["result"] = approximation
    return projection


def project_math_value(value: MathValue, name: str | None = None) -> JSONDict:
    if isinstance(value, bool):
        return {
            "result_text": "true" if value else "false",
            "result_type": RESULT_TYPE_BOOLEAN,
            "exact": True,
        }
    if is_strict_int(value):
        return project_integer(value, name)
    real = 0.0 if value == 0 else value
    return {
        "result": real,
        "result_text": format_real_number(real),
        "result_type": RESULT_TYPE_REAL,
        "exact": False,
        "working_digits": sys.float_info.dig,
    }


def project_math_evaluation[ValueT](
    evaluation: MathEvaluation[ValueT],
    *,
    project_value: Callable[[ValueT, str | None], JSONDict],
) -> JSONDict:
    projection = project_value(evaluation.value, None)
    if evaluation.assignments:
        assignments: list[JSONValue] = [
            {"name": assignment.name, **project_value(assignment.value, assignment.name)}
            for assignment in evaluation.assignments
        ]
        projection["assignments"] = assignments
    return projection
