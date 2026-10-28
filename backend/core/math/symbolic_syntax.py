"""SoAI - Symbolic syntax validation and exact literals [backend/core/math/symbolic_syntax.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
import math
from typing import TYPE_CHECKING

from sympy import Basic, I, Integer, Rational

from core.math.ast_evaluator import read_math_call
from core.math.errors import (
    MathExpressionError,
    build_multiple_results_error,
    build_unsupported_element_error,
    ensure_supported_comparisons,
)
from core.math.exact_integers import exact_decimal_ratio
from core.math.expression_parsing import read_binary_chain, read_real_literal
from core.math.function_catalog import MATH_MODE_SYMBOLIC, resolve_math_name
from core.math.symbolic_values import LIST_VALUE_MESSAGE

if TYPE_CHECKING:
    from core.math.symbolic_values import SymbolicEvaluationContext

__all__ = ("exact_rational", "read_symbolic_literal", "validate_symbolic_structure")


def exact_rational(value: int | float) -> Rational:
    return Rational(repr(value)) if isinstance(value, float) else Integer(value)


def read_symbolic_literal(node: ast.Constant, *, source: str) -> Basic:
    value = node.value
    token = ast.get_source_segment(source, node)
    if isinstance(value, float | complex) and token is not None:
        exact = Rational(*exact_decimal_ratio(token.rstrip("jJ").replace("_", "")))
        return exact * I if isinstance(value, complex) else exact
    if isinstance(value, complex):
        if not (math.isfinite(value.real) and math.isfinite(value.imag)):
            raise MathExpressionError("Numbers must be finite")
        return exact_rational(value.real) + exact_rational(value.imag) * I
    return exact_rational(read_real_literal(node))


def validate_symbolic_structure(
    node: ast.AST, context: SymbolicEvaluationContext, *, depth: int, allow_list: bool = False
) -> None:
    if depth > context.max_depth:
        raise MathExpressionError("Expression is too deeply nested")
    if isinstance(node, ast.Constant):
        read_symbolic_literal(node, source=context.source)
    elif isinstance(node, ast.Name):
        resolve_math_name(
            node.id, variables=context.variables, constants=context.constants, specs=context.specs
        )
    elif isinstance(node, ast.Call):
        _spec, arguments = read_math_call(node, mode=MATH_MODE_SYMBOLIC, specs=context.specs)
        for argument in arguments:
            validate_symbolic_structure(argument, context, depth=depth + 1, allow_list=True)
    elif isinstance(node, ast.BinOp):
        leftmost, links = read_binary_chain(node)
        for link in reversed(links):
            if not isinstance(
                link.op,
                ast.Add | ast.Sub | ast.Mult | ast.Div | ast.FloorDiv | ast.Mod | ast.Pow,
            ):
                raise build_unsupported_element_error(link.op)
        validate_symbolic_structure(leftmost, context, depth=depth + 1)
        for link in links:
            validate_symbolic_structure(link.right, context, depth=depth + 1)
    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ast.UAdd | ast.USub | ast.Not):
            raise build_unsupported_element_error(node.op)
        validate_symbolic_structure(node.operand, context, depth=depth + 1)
    elif isinstance(node, ast.Compare):
        ensure_supported_comparisons(node)
        for operand in [node.left, *node.comparators]:
            validate_symbolic_structure(operand, context, depth=depth + 1)
    elif isinstance(node, ast.BoolOp):
        for operand in node.values:
            validate_symbolic_structure(operand, context, depth=depth + 1)
    elif isinstance(node, ast.IfExp):
        for branch in (node.test, node.body, node.orelse):
            validate_symbolic_structure(branch, context, depth=depth + 1)
    elif isinstance(node, ast.Subscript):
        indices = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        if any(isinstance(index, ast.Slice) for index in indices):
            raise MathExpressionError(
                "Slices are not supported; index one element at a time, such as s[0]"
            )
        validate_symbolic_structure(node.value, context, depth=depth + 1)
        for index in indices:
            validate_symbolic_structure(index, context, depth=depth + 1)
    elif isinstance(node, ast.List):
        if not allow_list:
            raise build_multiple_results_error(LIST_VALUE_MESSAGE)
        for element in node.elts:
            validate_symbolic_structure(element, context, depth=depth + 1, allow_list=True)
    else:
        raise build_unsupported_element_error(node)
