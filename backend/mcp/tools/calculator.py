"""SoAI - MCP calculator tool implementation [backend/mcp/tools/calculator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.math.errors import MathExpressionError
from core.math.expression_evaluator import evaluate_math_expression
from core.types.json import JSONValue, is_json_dict
from core.validation.integers import is_strict_int
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_calculator",)

_ALLOWED_KEYS: frozenset[str] = frozenset({"expression", "variables"})


def _coerce_variables_map(value: JSONValue | None) -> dict[str, int | float] | None:
    if value is None:
        return None
    if not is_json_dict(value):
        raise MCPToolError(
            -32602,
            "Parameter 'variables' must be an object mapping names to numbers",
        )
    resolved: dict[str, int | float] = {}
    for key, raw_value in value.items():
        name = str(key or "").strip()
        if not name:
            raise MCPToolError(-32602, "Parameter 'variables' contains an empty name")
        if isinstance(raw_value, bool):
            raise MCPToolError(-32602, f"Variable '{name}' must be a number")
        if is_strict_int(raw_value):
            resolved[name] = int(raw_value)
            continue
        if isinstance(raw_value, float):
            resolved[name] = float(raw_value)
            continue
        raise MCPToolError(
            -32602,
            f"Variable '{name}' must be a number",
        )
    return resolved


async def tool_calculator(_utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    expression_value = get_arg(arguments, "expression")
    if not isinstance(expression_value, str) or not expression_value.strip():
        raise MCPToolError(-32602, "Parameter 'expression' must be a non-empty string")
    expression = expression_value.strip()
    variables = _coerce_variables_map(arguments.get("variables"))
    try:
        result = evaluate_math_expression(
            expression,
            variables=variables,
        )
    except MathExpressionError as exception:
        raise MCPToolError(-32602, exception.message) from exception
    return {"result": result, "expression": expression}
