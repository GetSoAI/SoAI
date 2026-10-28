"""SoAI - MCP calculator tool implementation [backend/mcp/tools/calculator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.concurrency.cancellation import CancellationToken
from core.concurrency.context import create_system_cancellation_id
from core.concurrency.deadlines import deadline_after
from core.math.errors import MathExpressionError
from core.math.expression_evaluator import evaluate_math_expression
from core.math.function_catalog import MATH_MODE_NUMERIC, MATH_MODE_SYMBOLIC, MATH_MODES
from core.math.result_projection import project_math_evaluation, project_math_value
from core.timing.constants import CONTROL_TIMEOUT_SEC
from mcp.tools.argument_fields import (
    reject_unexpected_parameters,
    require_non_empty_string,
    require_string_choice,
)
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.concurrency.deadlines import MonotonicDeadline
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("tool_calculator",)

_ALLOWED_KEYS: frozenset[str] = frozenset({"expression", "variables", "mode"})
_EXPRESSION_MESSAGE = "Parameter 'expression' must be a non-empty string"


async def tool_calculator(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    expression = require_non_empty_string(
        get_arg(arguments, "expression"),
        key="expression",
        type_message=_EXPRESSION_MESSAGE,
        empty_message=_EXPRESSION_MESSAGE,
    )
    mode_value = arguments.get("mode")
    mode = (
        MATH_MODE_NUMERIC
        if mode_value is None
        else require_string_choice(mode_value, key="mode", choices=MATH_MODES)
    )
    variables = arguments.get("variables")
    try:
        if mode == MATH_MODE_SYMBOLIC:
            projection = await utility_tools.symbolic_math_runner.evaluate(expression, variables)
        else:
            cancellation = CancellationToken(
                create_system_cancellation_id("mcp.calculator.numeric")
            )
            try:
                projection = await run_bounded_blocking_call(
                    utility_tools.numeric_math_pool,
                    _calculate_numeric,
                    expression,
                    variables,
                    deadline_after(CONTROL_TIMEOUT_SEC),
                    cancellation,
                    total_timeout_sec=CONTROL_TIMEOUT_SEC,
                )
            except TimeoutError as exception:
                cancellation.cancel("Numeric calculation deadline expired.")
                raise MCPToolError(
                    -32603,
                    f"Numeric evaluation exceeded the {CONTROL_TIMEOUT_SEC:g}-second limit; simplify the expression or retry when other calculations finish",
                ) from exception
            except asyncio.CancelledError:
                cancellation.cancel("Numeric calculation cancelled.")
                raise
    except MathExpressionError as exception:
        raise MCPToolError(-32602, exception.message) from exception
    return {"expression": expression, **projection}


def _calculate_numeric(
    expression: str,
    variables: JSONValue | None,
    deadline: MonotonicDeadline,
    cancellation_token: CancellationTokenProtocol,
) -> JSONDict:
    evaluation = evaluate_math_expression(
        expression, variables=variables, deadline=deadline, cancellation_token=cancellation_token
    )
    return project_math_evaluation(evaluation, project_value=project_math_value)
