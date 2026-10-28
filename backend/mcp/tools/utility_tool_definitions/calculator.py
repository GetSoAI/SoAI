"""SoAI - MCP utility tool definition: calculator [backend/mcp/tools/utility_tool_definitions/calculator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.math.expression_limits import MAX_RESULT_DIGITS
from core.math.function_catalog import (
    MATH_MODES,
    build_math_function_specs,
    describe_math_functions,
)
from core.math.result_projection import MATH_OUTCOMES, RESULT_TYPES
from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from core.timing.constants import CONTROL_TIMEOUT_SEC
from mcp.tools.icons import ICON_CALC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_calculator_tool_definitions",)

_VALUE_REFERENCE = "#/$defs/value"


def build_calculator_tool_definitions() -> dict[str, JSONDict]:
    specs = build_math_function_specs().values()
    numeric_functions = describe_math_functions(spec for spec in specs if spec.numeric)
    symbolic_functions = describe_math_functions(spec for spec in specs if not spec.numeric)
    value_properties = _value_properties()
    return {
        "calculator": {
            "title": "Calculator",
            "description": f"Safely evaluate math. Mode 'numeric' (default): exact integers (up to {MAX_RESULT_DIGITS} digits), floating-point decimals, + - * / // % ^, comparisons, and/or/not, 'a if c else b'. Separate statements with ';' or new lines; the last is the result and every 'name = value' is returned in 'assignments', so name each value you need. Constants pi, e, tau. Functions: {numeric_functions}; sum, mean and similar also take one list. Mode 'symbolic': unknown names are symbols, decimals are exact, I and oo exist; adds {symbolic_functions}. Write equations with == (a plain expression means = 0), e.g. solve([x + 2*y == 7, 3*x - y == 7], [x, y]). Index results with s[0], s[0][x] or M[i, j]; limits are two-sided unless side is 1 or -1. Symbolic calls stop after {CONTROL_TIMEOUT_SEC:g} s. Pass unknowns explicitly; other symbols are parameters, and answers that depend on them come as 'cases'. Results report 'exact' and any 'constraints' the value needs; special cases (partial or conditional solutions, no solution, infinitely many, infinity, undefined, no limit) add 'outcome' and 'note'.",
            "icons": [build_tool_icon_entry(ICON_CALC)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math to evaluate. Examples: '2^8', 'sin(pi/2)', 'factorial(30)', 'r = 3; pi * r^2', 'x > 0 and x < 10'",
                    },
                    "variables": {
                        "type": "object",
                        "description": 'Optional variables (name -> number), e.g. {"x": 1.5}',
                        "additionalProperties": {"type": "number"},
                    },
                    "mode": {
                        "type": "string",
                        "enum": list(MATH_MODES),
                        "description": "'numeric' (default) for calculations, 'symbolic' for exact algebra, equation solving, calculus and matrices",
                    },
                },
                "required": ["expression"],
            },
            "output_schema": {
                "type": "object",
                "$defs": {
                    "value": {
                        "type": "object",
                        "properties": value_properties,
                        "required": ["result_text", "result_type", "exact"],
                    }
                },
                "properties": {
                    **value_properties,
                    "expression": {
                        "type": "string",
                        "description": "Human-readable expression",
                    },
                    "assignments": {
                        "type": "array",
                        "description": "Values of 'name = expression' statements",
                        "items": _labeled_value("name"),
                    },
                },
            },
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=False,
            ),
        },
    }


def _value_properties() -> JSONDict:
    return {
        "result": {
            "type": "number",
            "description": "The value as a JSON number when it is real and finite; approximate beyond 2^53",
        },
        "result_text": {
            "type": "string",
            "description": "The value as text: exact when 'exact' is true, otherwise a decimal approximation",
        },
        "result_type": {"type": "string", "enum": list(RESULT_TYPES)},
        "exact": {
            "type": "boolean",
            "description": "True when every number in the value is exact; false when any part is a decimal approximation",
        },
        "working_digits": {
            "type": "integer",
            "description": "Decimal digits an approximate value is carried with. Not a count of correct digits: rounding and cancellation lose accuracy, so apply N(...) as the last step",
        },
        "outcome": {
            "type": "string",
            "enum": list(MATH_OUTCOMES),
            "description": "Kind of special result, such as no_solution, partial_solutions, conditional or no_limit",
        },
        "note": {"type": "string", "description": "Plain-language meaning of the outcome"},
        "items": {
            "type": "array",
            "description": "Each list entry or solution as its own result",
            "items": {"$ref": _VALUE_REFERENCE},
        },
        "values": {
            "type": "object",
            "description": "Solved value of each unknown, keyed by its name",
            "additionalProperties": {"$ref": _VALUE_REFERENCE},
        },
        "cases": {
            "type": "array",
            "description": "For outcome 'conditional': the result under each parameter condition",
            "items": _labeled_value("condition"),
        },
        "constraints": {
            "type": "array",
            "description": "Conditions the value needs, such as x != 0, because the original expression is undefined elsewhere; substituting a value that breaks one gives nan",
            "items": {"type": "string"},
        },
        "entries": {
            "type": "array",
            "description": "Matrix rows of entries as text, exact unless 'exact' is false",
            "items": {"type": "array", "items": {"type": "string"}},
        },
        "components": {
            "type": "object",
            "description": "Real and imaginary parts of a complex number",
            "properties": {
                "real": {"$ref": _VALUE_REFERENCE},
                "imaginary": {"$ref": _VALUE_REFERENCE},
            },
            "required": ["real", "imaginary"],
        },
    }


def _labeled_value(label: str) -> JSONDict:
    return {
        "allOf": [{"$ref": _VALUE_REFERENCE}],
        "properties": {label: {"type": "string"}},
        "required": [label],
    }
