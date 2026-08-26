"""SoAI - MCP base64 encoding/decoding tool implementation [backend/mcp/tools/encoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.serialization.base64_values import (
    decode_base64_ascii,
    decode_base64_ascii_urlsafe,
    encode_base64_ascii,
    encode_base64_urlsafe_ascii,
)
from mcp.tools.argument_fields import (
    reject_unexpected_parameters,
    require_string,
    require_string_choice,
)
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_base64",)

_ALLOWED_KEYS: frozenset[str] = frozenset({"operation", "text", "variant"})


async def tool_base64(_utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    operation_value = get_arg(arguments, "operation")
    operation = require_string(operation_value, key="operation")
    text = require_string(get_arg(arguments, "text"), key="text")
    variant_raw = arguments.get("variant", "base64")
    variant = require_string_choice(
        variant_raw,
        key="variant",
        choices=("base64", "base64url", "base32"),
    )
    if operation == "encode":
        text_bytes = text.encode("utf-8")
        if variant == "base64":
            result = encode_base64_ascii(text_bytes)
        elif variant == "base64url":
            result = encode_base64_urlsafe_ascii(text_bytes)
        else:
            result = base64.b32encode(text_bytes).decode("ascii")
    elif operation == "decode":
        try:
            if variant == "base64":
                result = decode_base64_ascii(text, error_message=f"Invalid {variant} input").decode(
                    "utf-8",
                )
            elif variant == "base64url":
                result = decode_base64_ascii_urlsafe(
                    text,
                    error_message=f"Invalid {variant} input",
                ).decode("utf-8")
            else:
                result = base64.b32decode(text, casefold=True).decode("utf-8")
        except ValidationError as exception:
            raise MCPToolError(-32602, exception.message) from exception
        except RECOVERABLE_EXCEPTIONS as exception:
            raise MCPToolError(-32602, f"Invalid {variant} input: {exception}") from exception
    else:
        raise MCPToolError(-32602, f"Unknown operation: {operation}. Valid: encode, decode")
    return {"result": result, "operation": operation, "variant": variant}
