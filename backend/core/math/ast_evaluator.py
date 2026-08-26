"""SoAI - Math AST evaluator [backend/core/math/ast_evaluator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
import math
from collections.abc import Callable

from core.math.errors import MathExpressionError
from core.validation.integers import is_strict_int

__all__ = (
    "count_nodes",
    "eval_node",
)


def count_nodes(parsed: ast.AST) -> int:
    return sum(1 for _node in ast.walk(parsed))


def eval_node(
    node: ast.AST,
    *,
    variables: dict[str, int | float],
    allowed_functions: dict[str, Callable[..., float | int]],
    allowed_constants: dict[str, float],
    depth: int,
    max_depth: int,
) -> int | float:
    if depth > max_depth:
        raise MathExpressionError("Expression is too deeply nested")

    if isinstance(node, ast.Expression):
        return eval_node(
            node.body,
            variables=variables,
            allowed_functions=allowed_functions,
            allowed_constants=allowed_constants,
            depth=depth + 1,
            max_depth=max_depth,
        )

    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool):
            raise MathExpressionError("Booleans are not allowed in expressions")
        if is_strict_int(value):
            return int(value)
        if isinstance(value, float):
            try:
                number = float(value)
            except OverflowError as exception:
                raise MathExpressionError("Number is too large") from exception
            if not math.isfinite(number):
                raise MathExpressionError("Numbers must be finite")
            return number
        raise MathExpressionError(f"Unsupported expression element: {type(node).__name__}")

    if isinstance(node, ast.UnaryOp):
        operand = eval_node(
            node.operand,
            variables=variables,
            allowed_functions=allowed_functions,
            allowed_constants=allowed_constants,
            depth=depth + 1,
            max_depth=max_depth,
        )
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise MathExpressionError(f"Unsupported expression element: {type(node.op).__name__}")

    if isinstance(node, ast.BinOp):
        left = eval_node(
            node.left,
            variables=variables,
            allowed_functions=allowed_functions,
            allowed_constants=allowed_constants,
            depth=depth + 1,
            max_depth=max_depth,
        )
        right = eval_node(
            node.right,
            variables=variables,
            allowed_functions=allowed_functions,
            allowed_constants=allowed_constants,
            depth=depth + 1,
            max_depth=max_depth,
        )
        try:
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise MathExpressionError("Division by zero")
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                if right == 0:
                    raise MathExpressionError("Division by zero")
                return left // right
            if isinstance(node.op, ast.Mod):
                if right == 0:
                    raise MathExpressionError("Modulo by zero")
                return left % right
            if isinstance(node.op, ast.Pow):
                try:
                    return float(math.pow(left, right))
                except (OverflowError, ValueError) as exception:
                    raise MathExpressionError(
                        f"Invalid power operation: {exception}"
                    ) from exception
        except OverflowError as exception:
            raise MathExpressionError("Result is too large") from exception
        except ZeroDivisionError as exception:
            message = "Modulo by zero" if isinstance(node.op, ast.Mod) else "Division by zero"
            raise MathExpressionError(message) from exception
        raise MathExpressionError(f"Unsupported expression element: {type(node.op).__name__}")

    if isinstance(node, ast.Name):
        name = str(node.id or "").strip()
        if name in variables:
            return variables[name]
        constant = allowed_constants.get(name)
        if constant is not None:
            return float(constant)
        if name in allowed_functions:
            raise MathExpressionError(f"'{name}' is a function; call it like {name}(...)")
        raise MathExpressionError(f"Unknown name: {name}")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise MathExpressionError("Only direct function calls are allowed (e.g. sin(x))")
        fn_name = str(node.func.id or "").strip()
        fn = allowed_functions.get(fn_name)
        if fn is None:
            raise MathExpressionError(f"Unknown function: {fn_name}")
        if node.keywords:
            raise MathExpressionError("Keyword arguments are not supported")
        args = [
            eval_node(
                arg,
                variables=variables,
                allowed_functions=allowed_functions,
                allowed_constants=allowed_constants,
                depth=depth + 1,
                max_depth=max_depth,
            )
            for arg in node.args
        ]
        try:
            result = fn(*args)
        except (OverflowError, ValueError, TypeError, ZeroDivisionError) as exception:
            raise MathExpressionError(f"Invalid call to {fn_name}(...): {exception}") from exception
        if isinstance(result, bool):
            raise MathExpressionError("Function returned a boolean result")
        if isinstance(result, int | float) and not isinstance(result, bool):
            try:
                number = float(result)
            except OverflowError as exception:
                raise MathExpressionError("Result is too large") from exception
            if not math.isfinite(number):
                raise MathExpressionError("Result is not a finite number")
            if is_strict_int(result):
                return int(result)
            return number
        raise MathExpressionError(f"Function {fn_name}(...) returned a non-number result")

    node_name = type(node).__name__
    raise MathExpressionError(f"Unsupported expression element: {node_name}")
