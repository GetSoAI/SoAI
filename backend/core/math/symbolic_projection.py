"""SoAI - JSON projection of symbolic math results [backend/core/math/symbolic_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from sympy import (
    AccumBounds,
    Basic,
    Derivative,
    Dict,
    Expr,
    Float,
    ImmutableMatrix,
    Integer,
    Integral,
    Limit,
    Product,
    Rational,
    Sum,
    nan,
    oo,
    sstr,
    zoo,
)
from sympy.core.evalf import prec_to_dps
from sympy.logic.boolalg import BooleanAtom

from core.math.errors import MathExpressionError
from core.math.expression_limits import MAX_RESULT_TEXT_CHARS
from core.math.result_projection import (
    OUTCOME_BOUNDED_OSCILLATION,
    OUTCOME_COMPLEX_INFINITY,
    OUTCOME_INFINITE,
    OUTCOME_NO_LIMIT,
    OUTCOME_UNDEFINED,
    OUTCOME_UNEVALUATED,
    RESULT_TYPE_COMPLEX,
    RESULT_TYPE_EXPRESSION,
    RESULT_TYPE_INFINITY,
    RESULT_TYPE_LIST,
    RESULT_TYPE_MATRIX,
    RESULT_TYPE_RATIONAL,
    RESULT_TYPE_REAL,
    RESULT_TYPE_SOLUTION,
    RESULT_TYPE_SOLUTIONS,
    RESULT_TYPE_UNDEFINED,
    describe_result_target,
    ensure_displayable_integer,
    project_integer,
    project_math_value,
)
from core.math.symbolic_domain import active_restrictions
from core.math.symbolic_exclusions import describe_constraints
from core.math.symbolic_precision import evaluate_symbolic_precision
from core.math.symbolic_values import SymbolicOutcome, float_precision_bits
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from core.math.symbolic_values import DomainRestriction, SymbolicValue
    from core.types.json import JSONDict, JSONValue

__all__ = ("project_symbolic_value",)

_APPROXIMATION_DIGITS = 17
_UNEVALUATED_TYPES: tuple[type[Basic], ...] = (Derivative, Integral, Limit, Sum, Product)


def project_symbolic_value(
    value: SymbolicValue,
    name: str | None = None,
    restrictions: Sequence[DomainRestriction] = (),
) -> JSONDict:
    projection = _project_value(value, name, restrictions)
    _check_text_length(str(projection["result_text"]), name)
    if isinstance(value, SymbolicOutcome):
        return projection
    constraints = describe_constraints(
        restrictions
        if isinstance(value, Dict)
        else active_restrictions(restrictions, _parts(value))
    )
    if sum(len(constraint) for constraint in constraints) > MAX_RESULT_TEXT_CHARS:
        raise MathExpressionError(
            f"The conditions that {describe_result_target(name).lower()} needs are too long to display; simplify the expression first"
        )
    if constraints:
        projection["constraints"] = [*constraints]
    return projection


def _project_value(
    value: SymbolicValue, name: str | None, restrictions: Sequence[DomainRestriction]
) -> JSONDict:
    if isinstance(value, SymbolicOutcome):
        return _project_outcome(value, name)
    if isinstance(value, list):
        return _with_parts(
            {"result_text": _symbolic_text(value, name), "result_type": RESULT_TYPE_LIST},
            "items",
            [project_symbolic_value(item, name, restrictions) for item in value],
        )
    if isinstance(value, ImmutableMatrix):
        projection: JSONDict = {
            "result_text": _symbolic_text(value, name),
            "result_type": RESULT_TYPE_MATRIX,
            "entries": [[_symbolic_text(entry, name) for entry in row] for row in value.tolist()],
        }
        return {**projection, **_exactness(value.atoms(Float))}
    if isinstance(value, Dict):
        return _project_solution(value, name, restrictions)
    if isinstance(value, BooleanAtom):
        return project_math_value(bool(value), name)
    if isinstance(value, Integer):
        return project_integer(int(value), name)
    special = _project_special_value(value)
    if special is not None:
        return special
    return {**_project_expression(value, name), **_exactness(value.atoms(Float))}


def _parts(value: SymbolicValue) -> list[Basic]:
    if isinstance(value, list):
        return [part for item in value for part in _parts(item)]
    return [value] if isinstance(value, Basic) else []


def _project_special_value(value: Basic) -> JSONDict | None:
    if value == oo:
        projection: JSONDict = {
            "result_text": "oo",
            "result_type": RESULT_TYPE_INFINITY,
            "outcome": OUTCOME_INFINITE,
            "note": "positive infinity: the value grows without bound, so a sum or limit equal to it diverges",
        }
    elif value == -oo:
        projection = {
            "result_text": "-oo",
            "result_type": RESULT_TYPE_INFINITY,
            "outcome": OUTCOME_INFINITE,
            "note": "negative infinity: the value decreases without bound, so a sum or limit equal to it diverges",
        }
    elif value == zoo:
        projection = {
            "result_text": "zoo",
            "result_type": RESULT_TYPE_INFINITY,
            "outcome": OUTCOME_COMPLEX_INFINITY,
            "note": "complex infinity: the value is unbounded without a single direction, as in division by zero",
        }
    elif value == nan:
        projection = {
            "result_text": "nan",
            "result_type": RESULT_TYPE_UNDEFINED,
            "outcome": OUTCOME_UNDEFINED,
            "note": "the expression has no defined value",
        }
    else:
        return None
    return {**projection, "exact": True}


def _project_expression(value: Basic, name: str | None) -> JSONDict:
    if isinstance(value, Rational):
        numerator = ensure_displayable_integer(int(value.p), name=name)
        denominator = ensure_displayable_integer(int(value.q), name=name)
        return _with_approximation(
            {"result_text": f"{numerator}/{denominator}", "result_type": RESULT_TYPE_RATIONAL},
            float(value),
        )
    if isinstance(value, Float):
        return _with_approximation(
            {"result_text": _symbolic_text(value, name), "result_type": RESULT_TYPE_REAL},
            float(value),
        )
    projection: JSONDict = {
        "result_text": _symbolic_text(value, name),
        "result_type": RESULT_TYPE_EXPRESSION,
    }
    if isinstance(value, AccumBounds):
        projection["outcome"] = OUTCOME_BOUNDED_OSCILLATION
        projection["note"] = "there is no single value: it keeps oscillating within these bounds"
        return projection
    if value.has(*_UNEVALUATED_TYPES):
        projection["outcome"] = OUTCOME_UNEVALUATED
        projection["note"] = (
            "no closed form is reported: the operation remains unevaluated; substitute parameter values or simplify it before applying N(...)"
        )
        return projection
    if isinstance(value, Expr) and value.is_number:
        real, imaginary = (value, Integer(0)) if value.is_real is True else value.as_real_imag()
        if imaginary.is_zero is True:
            try:
                approximation = evaluate_symbolic_precision(real, _APPROXIMATION_DIGITS)
            except MathExpressionError:
                try:
                    approximation = evaluate_symbolic_precision(
                        real, _APPROXIMATION_DIGITS, absolute_error=True
                    )
                except MathExpressionError:
                    projection["note"] = (
                        "No reliable decimal approximation was found; simplify the exact expression to reduce cancellation"
                    )
                    return projection
                projection["note"] = (
                    f"The decimal approximation has an absolute error below 1e-{_APPROXIMATION_DIGITS}; relative accuracy could not be established"
                )
            if isinstance(approximation, Float | Rational):
                return _with_approximation(projection, float(approximation))
            return projection
        if imaginary.is_zero is False:
            projection["result_type"] = RESULT_TYPE_COMPLEX
            projection["components"] = {
                "real": project_symbolic_value(real, name),
                "imaginary": project_symbolic_value(imaginary, name),
            }
    return projection


def _project_outcome(outcome: SymbolicOutcome, name: str | None) -> JSONDict:
    projection: JSONDict = {
        "result_text": outcome.text,
        "result_type": (
            RESULT_TYPE_UNDEFINED if outcome.outcome == OUTCOME_NO_LIMIT else RESULT_TYPE_SOLUTIONS
        ),
        "outcome": outcome.outcome,
        "note": outcome.note,
    }
    if outcome.cases:
        return _with_parts(
            projection,
            "cases",
            [
                {"condition": condition, **project_symbolic_value(case, name)}
                for condition, case in outcome.cases
            ],
        )
    if outcome.items:
        return _with_parts(
            projection,
            "items",
            [
                project_symbolic_value(item, name, outcome.restrictions_of(item))
                for item in outcome.items
            ],
        )
    return {**projection, **_exactness(outcome.approximate_numbers)}


def _project_solution(
    solution: Dict, name: str | None, restrictions: Sequence[DomainRestriction]
) -> JSONDict:
    values: dict[str, JSONDict] = {
        sstr(variable): project_symbolic_value(value, name, restrictions)
        for variable, value in sorted(solution.items(), key=lambda pair: sstr(pair[0]))
    }
    return _with_parts(
        {"result_text": _symbolic_text(solution, name), "result_type": RESULT_TYPE_SOLUTION},
        "values",
        list(values.values()),
        values,
    )


def _with_parts(
    projection: JSONDict, key: str, parts: list[JSONDict], stored: JSONValue | None = None
) -> JSONDict:
    projection[key] = parts if stored is None else stored
    projection["exact"] = all(part.get("exact") is True for part in parts)
    precisions = [digits for part in parts if is_strict_int(digits := part.get("working_digits"))]
    if precisions:
        projection["working_digits"] = min(precisions)
    return projection


def _exactness(approximate: Collection[Float]) -> JSONDict:
    if not approximate:
        return {"exact": True}
    return {
        "exact": False,
        "working_digits": min(prec_to_dps(float_precision_bits(number)) for number in approximate),
    }


def _with_approximation(projection: JSONDict, approximation: float) -> JSONDict:
    if math.isfinite(approximation):
        projection["result"] = 0.0 if approximation == 0 else approximation
    return projection


def _symbolic_text(value: SymbolicValue, name: str | None) -> str:
    if isinstance(value, SymbolicOutcome):
        return value.text
    if isinstance(value, list):
        text = f"[{', '.join(_symbolic_text(item, name) for item in value)}]"
    else:
        try:
            text = (
                f"Matrix({sstr(value.tolist())})"
                if isinstance(value, ImmutableMatrix)
                else sstr(value)
            )
        except ValueError as exception:
            raise MathExpressionError(
                f"{describe_result_target(name)} is too large to display"
            ) from exception
    _check_text_length(text, name)
    return text


def _check_text_length(text: str, name: str | None) -> None:
    if len(text) > MAX_RESULT_TEXT_CHARS:
        raise MathExpressionError(
            f"{describe_result_target(name)} is too long to display ({len(text)} characters); simplify it or evaluate it numerically with N(...)"
        )
