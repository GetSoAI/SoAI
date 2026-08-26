"""SoAI - MCP HTTP request validation helpers [backend/core/mcp/validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.external_service_exception import MCPError
from core.mcp.http_negotiation import accept_supports_json, accept_supports_sse
from core.validation.http_headers import content_type_is_json

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "get_required_argument",
    "validate_accept_header",
    "validate_content_type",
)


def get_required_argument(
    parameters: JSONDict,
    key: str,
    *,
    missing_message: str | None = None,
) -> JSONValue:
    if key not in parameters:
        raise MCPError(
            missing_message or f"Missing required parameter: {key}",
            rpc_code=-32602,
        )
    return parameters[key]


def validate_accept_header(accept: str) -> tuple[bool, bool]:
    return (
        accept_supports_json(accept),
        accept_supports_sse(accept),
    )


def validate_content_type(content_type: str | None) -> bool:
    return content_type_is_json(content_type)
