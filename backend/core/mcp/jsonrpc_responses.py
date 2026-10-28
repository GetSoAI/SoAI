"""SoAI - MCP JSON-RPC response construction [backend/core/mcp/jsonrpc_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.error_mapping import project_mcp_error_fields
from core.mcp.mcp_2025_11_25 import JSON_RPC_VERSION
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from core.errors.payload import ErrorPublicPayload

__all__ = ("build_error_response", "build_success_response")


def build_success_response(rpc_id: str | int | None, result: JSONValue) -> JSONDict:
    return {"jsonrpc": JSON_RPC_VERSION, "id": rpc_id, "result": result}


def build_error_response(
    rpc_id: str | int | None,
    code: int,
    message: str,
    data: JSONValue | None = None,
    *,
    public_error: ErrorPublicPayload | None = None,
) -> JSONDict:
    public_message, public_data = (
        (public_error.message, public_error.to_dict())
        if public_error is not None
        else project_mcp_error_fields(code, message, data)
    )
    payload: JSONDict = {"code": code, "message": public_message}
    if public_data is not None:
        payload["data"] = public_data
    return {"jsonrpc": JSON_RPC_VERSION, "id": rpc_id, "error": payload}
