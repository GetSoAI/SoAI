"""SoAI - MCP API route error adapters [backend/features/api/routes/mcp/route_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from fastapi import Request
from fastapi.responses import JSONResponse

from core.errors.external_service_exception import MCPError
from core.mcp.error_mapping import (
    build_mcp_error_payload,
    map_json_rpc_error_to_http_status,
    project_mcp_error_fields,
)
from core.types.json_value import filter_json_mapping_strict
from features.api.runtime.context import raise_api_error
from features.api.runtime.response_body import create_json_body_response

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_mcp_management_error_response",
    "raise_mcp_route_error",
)


def build_mcp_management_error_response(*, status_code: int, message: str) -> JSONResponse:
    return create_json_body_response(
        status_code=status_code,
        content=filter_json_mapping_strict(
            build_mcp_error_payload(message),
            error_message="MCP error payload must be JSON-compatible.",
        ),
    )


def raise_mcp_route_error(
    request: Request,
    exception: MCPError,
    *,
    error_type: str,
) -> NoReturn:
    public_message, public_data = project_mcp_error_fields(
        exception.rpc_code,
        exception.message,
        exception.rpc_data,
    )
    extra: JSONDict = {"code": int(exception.rpc_code)}
    if public_data is not None:
        extra["data"] = public_data
    raise_api_error(
        request,
        map_json_rpc_error_to_http_status(int(exception.rpc_code)),
        error_type,
        public_message,
        extra=extra,
    )
