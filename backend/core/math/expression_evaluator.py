"""SoAI - Math expression evaluator [backend/core/math/expression_evaluator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after
from core.math.allowed_symbols import (
    build_allowed_constants,
    build_allowed_functions,
)
from core.math.ast_evaluator import NumericEvaluationContext, eval_node
from core.math.errors import MathExpressionError
from core.math.expression_limits import (
    MAX_NESTING_DEPTH,
    MAX_NESTING_DEPTH_LIMIT,
    MAX_STATEMENT_NODES,
    MAX_STATEMENT_NODES_LIMIT,
)
from core.math.expression_parsing import parse_math_program
from core.math.expression_variables import coerce_variables_map
from core.math.function_catalog import build_math_function_specs
from core.math.program_evaluation import run_math_program
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.concurrency.deadlines import MonotonicDeadline
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.math.expression_parsing import MathStatement
    from core.math.program_evaluation import MathEvaluation, MathValue
    from core.types.json import JSONValue

__all__ = ("evaluate_math_expression",)


def _validate_evaluation_bounds(*, max_nodes: int, max_depth: int) -> None:
    if not is_strict_int(max_nodes):
        raise MathExpressionError("max_nodes must be an integer")
    if not is_strict_int(max_depth):
        raise MathExpressionError("max_depth must be an integer")
    if max_nodes <= 0 or max_nodes > MAX_STATEMENT_NODES_LIMIT:
        raise MathExpressionError("max_nodes is out of range")
    if max_depth <= 0 or max_depth > MAX_NESTING_DEPTH_LIMIT:
        raise MathExpressionError("max_depth is out of range")


def evaluate_math_expression(
    expression: str,
    *,
    variables: JSONValue | None = None,
    max_nodes: int = MAX_STATEMENT_NODES,
    max_depth: int = MAX_NESTING_DEPTH,
    deadline: MonotonicDeadline | None = None,
    cancellation_token: CancellationTokenProtocol | None = None,
) -> MathEvaluation[MathValue]:
    _validate_evaluation_bounds(max_nodes=max_nodes, max_depth=max_depth)
    execution_deadline = deadline if deadline is not None else deadline_after(CONTROL_TIMEOUT_SEC)
    constants = build_allowed_constants()
    scope: dict[str, MathValue] = {}
    scope.update(coerce_variables_map(variables, reserved_names=constants))
    program = parse_math_program(expression, reserved_names=constants, max_nodes=max_nodes)
    context = NumericEvaluationContext(
        variables=scope,
        functions=build_allowed_functions(
            deadline=execution_deadline, cancellation_token=cancellation_token
        ),
        constants=constants,
        specs=build_math_function_specs(),
        max_depth=max_depth,
        deadline=execution_deadline,
        cancellation_token=cancellation_token,
    )
    return run_math_program(
        program.statements,
        scope=scope,
        evaluate_statement=partial(_evaluate_numeric_statement, context=context),
    )


def _evaluate_numeric_statement(
    statement: MathStatement,
    *,
    context: NumericEvaluationContext,
) -> MathValue:
    try:
        value = eval_node(statement.expression, context, depth=1)
        context.check_execution()
        return value
    except OverflowError as exception:
        raise MathExpressionError("Result is too large") from exception
    except ArithmeticError as exception:
        raise MathExpressionError("Invalid arithmetic operation") from exception
