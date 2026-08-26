"""SoAI - MCP server-mode protocol negotiation [backend/features/api/routes/mcp/routes/server_mode_protocol.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.errors.exceptions import ValidationError
from core.mcp.jsonrpc_messages import resolve_jsonrpc_params_object
from core.mcp.mcp_2025_11_25 import MCP_PROTOCOL_VERSION_HEADER
from core.mcp.protocol_versions import validate_protocol_version
from features.api.routes.mcp.routes.server_mode_validation import (
    parse_protocol_version_or_raise,
)
from features.api.runtime.errors import raise_invalid_request

if TYPE_CHECKING:
    from core.mcp.protocols_main import MCPServerProtocol
    from core.types.json import JSONDict

__all__ = ("resolve_streamable_http_post_protocol_version",)


def resolve_streamable_http_post_protocol_version(
    request: Request,
    body: JSONDict,
    *,
    is_initialize: bool,
    mcp_server_instance: MCPServerProtocol | None = None,
    session_id: str | None = None,
) -> str:
    if not is_initialize:
        return _resolve_established_session_protocol_version(
            request,
            mcp_server_instance=mcp_server_instance,
            session_id=session_id,
        )
    try:
        params = resolve_jsonrpc_params_object(body.get("params", {}))
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    param_protocol_version = params.get("protocolVersion")
    if not isinstance(param_protocol_version, str) or not param_protocol_version.strip():
        raise_invalid_request(request, "Initialize params.protocolVersion is required.")
    param_valid, negotiated = validate_protocol_version(param_protocol_version.strip())
    if not param_valid:
        raise_invalid_request(
            request,
            f"Unsupported protocol version: {param_protocol_version.strip()}",
        )
    header_version = request.headers.get(MCP_PROTOCOL_VERSION_HEADER)
    if header_version:
        header_valid, normalized = validate_protocol_version(header_version)
        if not header_valid or normalized != negotiated:
            raise_invalid_request(
                request,
                "MCP-Protocol-Version header must match initialize protocolVersion.",
            )
    return negotiated


def _resolve_established_session_protocol_version(
    request: Request,
    *,
    mcp_server_instance: MCPServerProtocol | None,
    session_id: str | None,
) -> str:
    header_version = request.headers.get(MCP_PROTOCOL_VERSION_HEADER)
    session_protocol_version = _get_session_protocol_version(
        mcp_server_instance=mcp_server_instance,
        session_id=session_id,
    )
    if session_protocol_version is None:
        raise_invalid_request(request, "MCP-Protocol-Version header is required.")
    if header_version:
        normalized = parse_protocol_version_or_raise(request, detailed_error=True)
        if normalized != session_protocol_version:
            raise_invalid_request(
                request,
                "MCP-Protocol-Version header must match initialized session protocolVersion.",
            )
        return normalized
    return session_protocol_version


def _get_session_protocol_version(
    *,
    mcp_server_instance: MCPServerProtocol | None,
    session_id: str | None,
) -> str | None:
    if mcp_server_instance is None or session_id is None:
        return None
    session = mcp_server_instance.session.get_session(session_id)
    if session is None:
        return None
    protocol_version = session.protocol_version
    version_valid, normalized = validate_protocol_version(protocol_version)
    return normalized if version_valid else None
