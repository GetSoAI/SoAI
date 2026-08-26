"""SoAI - MCP random generator tool implementation [backend/mcp/tools/random_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import secrets
import string
import uuid
from typing import TYPE_CHECKING

from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("tool_random_generate",)

_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"type", "min", "max", "length", "charset", "choices", "count"},
)


async def tool_random_generate(
    _utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    gen_type_value = get_arg(arguments, "type")
    if not isinstance(gen_type_value, str):
        raise MCPToolError(-32602, f"type must be a string, got {type(gen_type_value).__name__}")
    gen_type = gen_type_value
    count_raw = arguments.get("count", 1)
    if isinstance(count_raw, bool) or not isinstance(count_raw, int | float):
        raise MCPToolError(-32602, f"count must be a number, got {type(count_raw).__name__}")
    count = min(100, max(1, int(count_raw)))
    values: list[JSONValue] = []
    if gen_type == "integer":
        values = _generate_integers(arguments, count)
    elif gen_type == "float":
        values = _generate_floats(arguments, count)
    elif gen_type == "uuid":
        for _ in range(count):
            values.append(str(uuid.uuid4()))
    elif gen_type == "string":
        values = _generate_strings(arguments, count)
    elif gen_type == "choice":
        values = _generate_choices(arguments, count)
    else:
        raise MCPToolError(-32602, f"Unknown type: {gen_type}")
    return {"values": values, "type": gen_type, "count": len(values)}


def _generate_integers(arguments: JSONDict, count: int) -> list[JSONValue]:
    min_raw, max_raw = (arguments.get("min", 0), arguments.get("max", 100))
    if (
        isinstance(min_raw, bool)
        or isinstance(max_raw, bool)
        or (not isinstance(min_raw, int | float))
        or (not isinstance(max_raw, int | float))
    ):
        raise MCPToolError(-32602, "min and max must be numbers")
    min_val, max_val = (int(min_raw), int(max_raw))
    if min_val > max_val:
        raise MCPToolError(-32602, "min must be less than or equal to max")
    values: list[JSONValue] = []
    for _ in range(count):
        values.append(secrets.randbelow(max_val - min_val + 1) + min_val)
    return values


def _generate_floats(arguments: JSONDict, count: int) -> list[JSONValue]:
    min_raw, max_raw = (arguments.get("min", 0.0), arguments.get("max", 1.0))
    if (
        isinstance(min_raw, bool)
        or isinstance(max_raw, bool)
        or (not isinstance(min_raw, int | float))
        or (not isinstance(max_raw, int | float))
    ):
        raise MCPToolError(-32602, "min and max must be numbers")
    min_float, max_float = (float(min_raw), float(max_raw))
    if min_float > max_float:
        raise MCPToolError(-32602, "min must be less than or equal to max")
    random_generator = secrets.SystemRandom()
    values: list[JSONValue] = []
    for _ in range(count):
        values.append(random_generator.uniform(min_float, max_float))
    return values


def _generate_strings(arguments: JSONDict, count: int) -> list[JSONValue]:
    length_raw = arguments.get("length", 16)
    if isinstance(length_raw, bool) or not isinstance(length_raw, int | float):
        raise MCPToolError(
            -32602,
            f"length must be a number, got {type(length_raw).__name__}",
        )
    length = min(1024, max(1, int(length_raw)))
    charset_name_raw = arguments.get("charset", "alphanumeric")
    if not isinstance(charset_name_raw, str):
        raise MCPToolError(
            -32602,
            f"charset must be a string, got {type(charset_name_raw).__name__}",
        )
    charset_name = charset_name_raw
    charset_map = {
        "alphanumeric": string.ascii_letters + string.digits,
        "alpha": string.ascii_letters,
        "numeric": string.digits,
        "hex": string.hexdigits[:16],
        "password": "".join((string.ascii_letters, string.digits, "!@#$%^&*()-_=+[]{}|;:,.<>?")),
    }
    charset = charset_map.get(charset_name)
    if charset is None:
        raise MCPToolError(
            -32602,
            f"Unknown charset: {charset_name}. Valid: {', '.join(charset_map.keys())}",
        )
    values: list[JSONValue] = []
    for _ in range(count):
        values.append("".join(secrets.choice(charset) for _ in range(length)))
    return values


def _generate_choices(arguments: JSONDict, count: int) -> list[JSONValue]:
    choices = arguments.get("choices")
    if not choices or not isinstance(choices, list) or not choices:
        raise MCPToolError(-32602, "choices must be a non-empty array")
    if not all(isinstance(choice, str) for choice in choices):
        raise MCPToolError(-32602, "All choices must be strings")
    values: list[JSONValue] = []
    for _ in range(count):
        values.append(secrets.choice(choices))
    return values
