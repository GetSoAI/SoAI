"""SoAI - MCP exception boundary RPC mapping [backend/mcp/shared/exception_boundary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.external_service_exception import MCPError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "resolve_mcp_boundary_rpc_code",
    "resolve_mcp_boundary_rpc_data",
)


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
