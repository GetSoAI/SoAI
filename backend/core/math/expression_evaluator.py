"""SoAI - Math expression evaluator [backend/core/math/expression_evaluator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
import math
from collections.abc import Callable

from core.math.allowed_symbols import (
    build_allowed_constants,
    build_allowed_functions,
)
from core.math.ast_evaluator import count_nodes, eval_node
from core.math.errors import MathExpressionError
from core.math.expression_text import (
    MAX_REWRITTEN_EXPRESSION_CHARS,
    normalize_expression_text,
    rewrite_common_operator_aliases,
)
from core.math.expression_variables import coerce_variables_map
from core.validation.integers import is_strict_int

__all__ = ("evaluate_math_expression",)


def _build_syntax_error_message(exception: SyntaxError) -> str:
    detail = str(exception.msg or "invalid syntax").strip() or "invalid syntax"
    lineno_raw = exception.lineno
    offset_raw = exception.offset
    if lineno_raw is None or offset_raw is None:
        return f"Invalid expression syntax: {detail}"
    lineno = int(lineno_raw)
    offset = int(offset_raw)
    if lineno <= 0 or offset <= 0:
        return f"Invalid expression syntax: {detail}"
    text_value = exception.text
    if isinstance(text_value, str):
        snippet = text_value.strip().replace("\t", " ")
        if snippet:
            if len(snippet) > 80:
                snippet = f"{snippet[:77].rstrip()}..."
            return (
                f"Invalid expression syntax at line {lineno}, column {offset}: {detail} "
                f"(near: {snippet})"
            )
    return f"Invalid expression syntax at line {lineno}, column {offset}: {detail}"


def evaluate_math_expression(
    expression: str,
    *,
    variables: dict[str, int | float | bool] | None = None,
    max_nodes: int = 400,
    max_depth: int = 64,
) -> float:
    if not is_strict_int(max_nodes):
        raise MathExpressionError("max_nodes must be an integer")
    if not is_strict_int(max_depth):
        raise MathExpressionError("max_depth must be an integer")
    if max_nodes <= 0 or max_nodes > 5000:
        raise MathExpressionError("max_nodes is out of range")
    if max_depth <= 0 or max_depth > 256:
        raise MathExpressionError("max_depth is out of range")

    normalized = normalize_expression_text(expression)
    rewritten = rewrite_common_operator_aliases(normalized)
    if len(rewritten) > MAX_REWRITTEN_EXPRESSION_CHARS:
        raise MathExpressionError("expression exceeds max length after normalization")

    resolved_variables = coerce_variables_map(variables)
    allowed_functions: dict[str, Callable[..., float | int]] = build_allowed_functions()
    allowed_constants: dict[str, float] = build_allowed_constants()
    reserved_names = (*allowed_functions.keys(), *allowed_constants.keys())
    for reserved_name in reserved_names:
        if reserved_name in resolved_variables:
            message = f"Variable name '{reserved_name}' is reserved"
            raise MathExpressionError(message)

    try:
        parsed = ast.parse(rewritten, mode="eval")
    except SyntaxError as exception:
        raise MathExpressionError(_build_syntax_error_message(exception)) from exception

    if count_nodes(parsed) > max_nodes:
        raise MathExpressionError("Expression is too complex")

    try:
        result = eval_node(
            parsed,
            variables=resolved_variables,
            allowed_functions=allowed_functions,
            allowed_constants=allowed_constants,
            depth=0,
            max_depth=max_depth,
        )
    except OverflowError as exception:
        raise MathExpressionError("Result is too large") from exception
    except ArithmeticError as exception:
        raise MathExpressionError("Invalid arithmetic operation") from exception
    try:
        number_result = float(result)
    except OverflowError as exception:
        raise MathExpressionError("Result is too large") from exception
    if not math.isfinite(number_result):
        raise MathExpressionError("Result is not a finite number")
    return number_result
