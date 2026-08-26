"""SoAI - MCP server-mode JSON-RPC HTTP body helpers [backend/features/api/routes/mcp/routes/server_mode_jsonrpc.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from fastapi import Response

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.mcp.error_mapping import map_json_rpc_error_to_http_status
from core.mcp.jsonrpc_responses import build_error_response
from core.serialization.json_parsing import MAX_JSON_NESTING_DEPTH, parse_json_value
from features.api.runtime.request_media_types import require_non_multipart_media_type
from features.api.runtime.response_body import create_json_body_response

if TYPE_CHECKING:
    from fastapi import Request

    from core.types.json import JSONDict, JSONValue

__all__ = (
    "create_jsonrpc_error_response",
    "read_jsonrpc_body_or_error_response",
)

LOGGER_NAME = "SoAI.features.api.server_mode_jsonrpc"
OPERATION_READ_JSONRPC_BODY = "api_mcp.server_mode.read_jsonrpc_body"


def create_jsonrpc_error_response(
    rpc_id: str | int | None,
    code: int,
    message: str,
    data: JSONValue | None = None,
    *,
    headers: Mapping[str, str] | None = None,
) -> Response:
    return create_json_body_response(
        content=build_error_response(rpc_id, code, message, data),
        status_code=map_json_rpc_error_to_http_status(code),
        headers=headers,
    )


async def read_jsonrpc_body_or_error_response(request: Request) -> JSONDict | Response:
    logger = get_logger(LOGGER_NAME)
    try:
        require_non_multipart_media_type(request)
        body = parse_json_value(
            await request.body(),
            field="MCP JSON-RPC body",
            max_depth=MAX_JSON_NESTING_DEPTH,
            strict_utf8=True,
        )
    except ValidationError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Invalid MCP server mode JSON-RPC body (non-critical).",
            operation=OPERATION_READ_JSONRPC_BODY,
            level="debug",
        )
        return create_jsonrpc_error_response(None, -32700, "Invalid JSON body.")
    if not isinstance(body, dict):
        return create_jsonrpc_error_response(None, -32600, "Invalid JSON-RPC message.")
    return body
