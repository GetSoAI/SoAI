"""SoAI - MCP JSON-RPC error helpers [backend/core/mcp/error_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "MCPErrorPayload",
    "build_mcp_error_payload",
    "map_json_rpc_error_to_http_status",
    "project_mcp_tool_error_fields",
    "project_mcp_error_fields",
)


class MCPErrorPayload(TypedDict):
    error: str


def build_mcp_error_payload(message: str) -> MCPErrorPayload:
    return {"error": message}


def map_json_rpc_error_to_http_status(code: int) -> int:
    return {
        -32700: 400,
        -32600: 400,
        -32602: 400,
        -32601: 404,
        -32603: 500,
        -32000: 429,
    }.get(code, 500)


def project_mcp_error_fields(
    code: int,
    message: str,
    data: JSONValue | None,
) -> tuple[str, JSONValue | None]:
    match int(code):
        case -32700 | -32600 | -32601 | -32602:
            return message, data
        case -32000:
            return "MCP rate limit exceeded.", None
        case _:
            return "Internal MCP error.", None


def project_mcp_tool_error_fields(
    code: int,
    message: str,
    data: JSONValue | None,
) -> tuple[str, JSONValue | None]:
    match int(code):
        case -32603:
            return message, data
        case _:
            return project_mcp_error_fields(code, message, data)
