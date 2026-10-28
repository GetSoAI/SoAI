"""SoAI - Math AST evaluator [backend/core/math/ast_evaluator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.math.errors import (
    MathDomainError,
    MathExpressionError,
    build_multiple_results_error,
    build_unsupported_element_error,
    ensure_supported_comparisons,
)
from core.math.expression_limits import MAX_ERROR_DETAIL_CHARS
from core.math.expression_parsing import read_binary_chain, read_real_literal
from core.math.function_catalog import (
    MATH_MODE_NUMERIC,
    MathFunctionSpec,
    require_math_function_spec,
    resolve_math_name,
    validate_math_call_arity,
)
from core.math.numeric_operators import (
    apply_binary_operator,
    apply_comparison,
    apply_unary_operator,
    ensure_finite_number,
    require_condition,
    require_number,
)

if TYPE_CHECKING:
    from core.concurrency.deadlines import MonotonicDeadline
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.math.program_evaluation import MathValue

__all__ = (
    "NumericEvaluationContext",
    "call_argument_nodes",
    "describe_function_failure",
    "eval_node",
    "read_math_call",
)

_LIST_ARGUMENT_MESSAGE = "Lists are only allowed as the single argument of functions that take several values, such as sum([1, 2, 3]) or mean([...])"
_FUNCTION_FAILURE_DESCRIPTIONS = (
    ("math domain error", "the argument is outside the function's domain"),
    ("math range error", "the result is outside the floating-point range"),
)


@dataclass(frozen=True, slots=True)
class NumericEvaluationContext:
    variables: Mapping[str, MathValue]
    functions: Mapping[str, Callable[..., int | float]]
    constants: Mapping[str, float]
    specs: Mapping[str, MathFunctionSpec]
    max_depth: int
    deadline: MonotonicDeadline | None = None
    cancellation_token: CancellationTokenProtocol | None = None

    def check_execution(self) -> None:
        if self.cancellation_token is not None:
            self.cancellation_token.raise_if_cancelled()
        if self.deadline is not None and self.deadline.expired():
            raise TimeoutError("Numeric evaluation deadline expired")


def eval_node(node: ast.AST, context: NumericEvaluationContext, *, depth: int) -> MathValue:
    context.check_execution()
    if depth > context.max_depth:
        raise MathExpressionError("Expression is too deeply nested")
    if isinstance(node, ast.Expression):
        return eval_node(node.body, context, depth=depth + 1)
    if isinstance(node, ast.Constant):
        return read_real_literal(node)
    if isinstance(node, ast.Name):
        return _resolve_name(node.id, context)
    if isinstance(node, ast.UnaryOp):
        operand = eval_node(node.operand, context, depth=depth + 1)
        return apply_unary_operator(node.op, operand)
    if isinstance(node, ast.BinOp):
        return _evaluate_binary_chain(node, context, depth=depth)
    if isinstance(node, ast.Compare):
        return _evaluate_comparison(node, context, depth=depth)
    if isinstance(node, ast.BoolOp):
        return _evaluate_boolean_operation(node, context, depth=depth)
    if isinstance(node, ast.IfExp):
        condition = require_condition(eval_node(node.test, context, depth=depth + 1))
        return eval_node(node.body if condition else node.orelse, context, depth=depth + 1)
    if isinstance(node, ast.Call):
        return _evaluate_call(node, context, depth=depth)
    if isinstance(node, ast.List):
        raise build_multiple_results_error(_LIST_ARGUMENT_MESSAGE)
    raise build_unsupported_element_error(node)


def call_argument_nodes(
    spec: MathFunctionSpec, arguments: Sequence[ast.expr]
) -> Sequence[ast.expr]:
    if spec.accepts_value_list and len(arguments) == 1 and isinstance(arguments[0], ast.List):
        return arguments[0].elts
    return arguments


def describe_function_failure(exception: BaseException) -> str:
    detail = str(exception).strip()
    for library_message, description in _FUNCTION_FAILURE_DESCRIPTIONS:
        if detail == library_message:
            return description
    if isinstance(exception, ZeroDivisionError):
        return "division by zero"
    if isinstance(exception, OverflowError):
        return "a value is too large for floating-point arithmetic"
    if isinstance(exception, LookupError | AttributeError):
        return "the symbolic engine could not handle this input; rewrite it or split it into steps"
    return detail[:MAX_ERROR_DETAIL_CHARS] or type(exception).__name__


def _resolve_name(name: str, context: NumericEvaluationContext) -> MathValue:
    value = resolve_math_name(
        name,
        variables=context.variables,
        constants=context.constants,
        specs=context.specs,
    )
    if value is None:
        raise MathExpressionError(
            f"Unknown name: {name} (pass its value in 'variables', assign it first with {name} = ..., or use mode 'symbolic' for symbols)"
        )
    return value


def _evaluate_binary_chain(
    node: ast.BinOp,
    context: NumericEvaluationContext,
    *,
    depth: int,
) -> MathValue:
    leftmost, links = read_binary_chain(node)
    value = eval_node(leftmost, context, depth=depth + 1)
    for link in links:
        right = eval_node(link.right, context, depth=depth + 1)
        value = apply_binary_operator(link.op, value, right)
    return value


def _evaluate_comparison(
    node: ast.Compare,
    context: NumericEvaluationContext,
    *,
    depth: int,
) -> bool:
    ensure_supported_comparisons(node)
    left = eval_node(node.left, context, depth=depth + 1)
    for operator, comparator in zip(node.ops, node.comparators, strict=True):
        right = eval_node(comparator, context, depth=depth + 1)
        if not apply_comparison(operator, left, right):
            return False
        left = right
    return True


def _evaluate_boolean_operation(
    node: ast.BoolOp,
    context: NumericEvaluationContext,
    *,
    depth: int,
) -> bool:
    stop_value = isinstance(node.op, ast.Or)
    for operand in node.values:
        if require_condition(eval_node(operand, context, depth=depth + 1)) is stop_value:
            return stop_value
    return not stop_value


def _evaluate_call(node: ast.Call, context: NumericEvaluationContext, *, depth: int) -> MathValue:
    spec, argument_nodes = read_math_call(node, mode=MATH_MODE_NUMERIC, specs=context.specs)
    arguments = [
        require_number(eval_node(argument, context, depth=depth + 1)) for argument in argument_nodes
    ]
    function = context.functions[spec.name]
    try:
        result = function(*arguments)
    except (MathDomainError, OverflowError, ValueError, TypeError, ZeroDivisionError) as exception:
        raise MathExpressionError(
            f"Invalid call to {spec.signature}: {describe_function_failure(exception)}"
        ) from exception
    if isinstance(result, bool) or not isinstance(result, int | float):
        raise MathExpressionError(f"Function {spec.name}(...) returned a non-number result")
    return ensure_finite_number(result)


def read_math_call(
    node: ast.Call, *, mode: str, specs: Mapping[str, MathFunctionSpec]
) -> tuple[MathFunctionSpec, Sequence[ast.expr]]:
    if not isinstance(node.func, ast.Name):
        raise MathExpressionError(
            "Only direct function calls are allowed (e.g. sin(x)); write multiplication explicitly, e.g. 2*(x + 1)"
        )
    name = node.func.id
    spec = require_math_function_spec(name, mode=mode, specs=specs)
    if node.keywords:
        raise MathExpressionError("Keyword arguments are not supported")
    argument_nodes = call_argument_nodes(spec, node.args)
    validate_math_call_arity(spec, len(argument_nodes))
    return spec, argument_nodes
