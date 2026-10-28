"""SoAI - MCP exception boundary RPC mapping [backend/mcp/shared/exception_boundary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.external_service_exception import MCPError
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "build_jsonrpc_error_from_mcp_error",
    "resolve_mcp_boundary_rpc_code",
    "resolve_mcp_boundary_rpc_data",
)


def build_jsonrpc_error_from_mcp_error(exception: MCPError) -> MCPJSONRPCError:
    rpc_error = MCPJSONRPCError(
        exception.rpc_code,
        exception.message,
        exception.rpc_data,
    )
    rpc_error.public_error = exception.public_error
    return rpc_error


def resolve_mcp_boundary_rpc_code(exception: Exception) -> int:
    if isinstance(exception, ValidationError):
        return -32602
    if isinstance(exception, MCPError):
        return int(exception.rpc_code)
    return -32603


def resolve_mcp_boundary_rpc_data(exception: Exception) -> JSONValue | None:
    if isinstance(exception, MCPError):
        return exception.rpc_data
    return None
