"""SoAI - MCP utility tools error types and dispatch guard [backend/mcp/tools/error.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.external_service_exception import MCPError
from core.errors.messages import resolve_error_message
from core.errors.public_projection import project_specific_public_error
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from core.types.json import JSONDict, JSONValue

__all__ = (
    "MCPToolError",
    "build_invalid_params_error",
    "get_arg",
    "guarded_tool_call",
    "tool_error_from_soai_error",
)

LOGGER_NAME = "SoAI.mcp.tools.error"


class MCPToolError(MCPError):
    def __init__(self, rpc_code: int, message: str, data: JSONValue | None = None) -> None:
        resolved_message = resolve_error_message(message, default_message="MCP tool failed.")
        super().__init__(
            resolved_message,
            rpc_code=rpc_code,
            rpc_data=data,
            details={"rpc_code": rpc_code, "data": data},
        )
        self.code = str(rpc_code)
        self.data = data

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return (((self.details or {}).get("rpc_code"), self.message, self.data), {})


def get_arg(args: JSONDict, key: str) -> JSONValue:
    if key not in args:
        raise MCPToolError(-32602, f"Missing required parameter: {key}")
    return args[key]


def build_invalid_params_error(message: str) -> MCPToolError:
    return MCPToolError(-32602, message)


def tool_error_from_soai_error(exception: SoAIError) -> MCPToolError:
    rpc_code = -32602 if isinstance(exception, ValidationError) else -32603
    public_error = project_specific_public_error(exception)
    if public_error is not None:
        tool_error = MCPToolError(rpc_code, public_error.message, public_error.to_dict())
        tool_error.public_error = public_error
        return tool_error
    return MCPToolError(rpc_code, exception.message)


async def guarded_tool_call(
    operation: str,
    tool_name: str,
    coro: Awaitable[JSONValue],
) -> JSONValue:
    try:
        return await coro
    except asyncio.CancelledError:
        raise
    except MCPToolError:
        raise
    except MCPError as exception:
        tool_error = MCPToolError(exception.rpc_code, exception.message, exception.rpc_data)
        tool_error.public_error = exception.public_error
        raise tool_error from exception
    except SoAIError as exception:
        raise tool_error_from_soai_error(exception) from exception
    except Exception as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(
            exception,
            operation=operation,
        )
        log_exception(
            logger,
            coerced,
            message="Tool invocation failed.",
            operation=operation,
            details={"tool_name": tool_name},
        )
        raise MCPToolError(-32603, coerced.message) from exception
