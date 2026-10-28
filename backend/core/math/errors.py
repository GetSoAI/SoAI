"""SoAI - Math expression errors [backend/core/math/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast

__all__ = (
    "UNSUPPORTED_COMPARISON_MESSAGE",
    "MathExpressionError",
    "MathDomainError",
    "build_multiple_results_error",
    "build_unsupported_element_error",
    "ensure_supported_comparisons",
)

_MULTIPLE_RESULTS_HINT = "to get several results, give each one a name (a = ...; b = ...), because every named value is returned"
UNSUPPORTED_COMPARISON_MESSAGE = (
    "Unsupported expression element: only the comparisons <, <=, >, >=, == and != are supported"
)
_SUPPORTED_COMPARISON_TYPES: tuple[type[ast.cmpop], ...] = (
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Eq,
    ast.NotEq,
)
_BITWISE_OPERATOR_TYPES: tuple[type[ast.AST], ...] = (
    ast.Invert,
    ast.BitAnd,
    ast.BitOr,
    ast.BitXor,
    ast.LShift,
    ast.RShift,
)
_TUPLE_ELEMENT_MESSAGE = "Unsupported expression element: commas only separate function arguments; use '.' for decimals (1.5) and ';' or a new line between statements"
_UNSUPPORTED_ELEMENT_DESCRIPTIONS: tuple[tuple[tuple[type[ast.AST], ...], str], ...] = (
    (_BITWISE_OPERATOR_TYPES, "bitwise operators are not supported"),
    ((ast.MatMult,), "the '@' operator is not supported; use '*'"),
    ((ast.Attribute,), "attribute access is not allowed"),
    (
        (ast.Subscript, ast.Slice),
        "indexing is only supported in mode 'symbolic', for lists, solutions and matrices",
    ),
    ((ast.Lambda,), "lambda expressions are not allowed"),
    ((ast.Dict, ast.Set), "sets and dictionaries are not supported"),
    (
        (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
        "comprehensions are not supported",
    ),
    ((ast.NamedExpr,), "use a 'name = value' statement instead of ':='"),
    ((ast.Starred,), "argument unpacking is not supported"),
)


class MathExpressionError(Exception):
    message: str

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = str(message)


class MathDomainError(MathExpressionError): ...


def ensure_supported_comparisons(node: ast.Compare) -> None:
    if not all(isinstance(operator, _SUPPORTED_COMPARISON_TYPES) for operator in node.ops):
        raise MathExpressionError(UNSUPPORTED_COMPARISON_MESSAGE)


def build_multiple_results_error(message: str) -> MathExpressionError:
    return MathExpressionError(f"{message}; {_MULTIPLE_RESULTS_HINT}")


def build_unsupported_element_error(node: ast.AST) -> MathExpressionError:
    if isinstance(node, ast.Tuple):
        return build_multiple_results_error(_TUPLE_ELEMENT_MESSAGE)
    if isinstance(node, ast.Constant) and isinstance(node.value, complex):
        return MathExpressionError(
            "Unsupported expression element: complex numbers require mode 'symbolic' (use I for the imaginary unit)"
        )
    for node_types, description in _UNSUPPORTED_ELEMENT_DESCRIPTIONS:
        if isinstance(node, node_types):
            return MathExpressionError(f"Unsupported expression element: {description}")
    return MathExpressionError(f"Unsupported expression element: {type(node).__name__}")
