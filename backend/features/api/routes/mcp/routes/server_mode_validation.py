"""SoAI - MCP server-mode request validation helpers [backend/features/api/routes/mcp/routes/server_mode_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request, status

from core.mcp.http_negotiation import resolve_streamable_http_post_response_mode
from core.mcp.mcp_2025_11_25 import (
    MCP_PROTOCOL_VERSION_HEADER,
    MCP_SESSION_ID_HEADER,
    validate_session_id_format,
)
from core.mcp.protocol_versions import (
    SUPPORTED_PROTOCOL_VERSIONS,
    validate_protocol_version,
)
from core.mcp.validation import (
    validate_accept_header,
    validate_content_type,
)
from features.api.runtime.context import raise_api_error
from features.api.runtime.errors import raise_bad_request, raise_service_unavailable

if TYPE_CHECKING:
    from core.mcp.protocols_main import MCPServerProtocol

__all__ = (
    "parse_protocol_version_or_raise",
    "require_accept",
    "require_content_type_json",
    "require_mcp_server_mode",
    "resolve_session_id_for_mode",
    "resolve_streamable_http_post_response_mode_or_raise",
    "validate_session_id_or_raise",
)


def validate_session_id_or_raise(request: Request, session_id: str) -> None:
    if not validate_session_id_format(session_id):
        raise_bad_request(
            request,
            "Session ID contains invalid characters",
            error_type="invalid_session_id",
        )


def require_mcp_server_mode(request: Request, mcp_server_instance: MCPServerProtocol) -> None:
    if not mcp_server_instance.server_mode_active:
        raise_service_unavailable(request, "MCP Server Mode is not active.")


def require_content_type_json(request: Request) -> None:
    content_type = request.headers.get("content-type", "")
    if not validate_content_type(content_type):
        raise_api_error(
            request,
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "unsupported_media_type",
            "Content-Type must be application/json",
        )


def require_accept(
    request: Request,
    *,
    need_json: bool = False,
    need_sse: bool = False,
    allow_any: bool = False,
) -> None:
    accept_header = request.headers.get("accept", "*/*")
    has_json, has_sse = validate_accept_header(accept_header)
    if need_json and need_sse:
        if allow_any:
            if not (has_json or has_sse):
                raise_api_error(
                    request,
                    status.HTTP_406_NOT_ACCEPTABLE,
                    "not_acceptable",
                    "Accept header must include application/json or text/event-stream",
                )
        elif not has_json or not has_sse:
            raise_api_error(
                request,
                status.HTTP_406_NOT_ACCEPTABLE,
                "not_acceptable",
                "Accept header must include application/json and text/event-stream",
            )
    elif need_json and (not has_json):
        raise_api_error(
            request,
            status.HTTP_406_NOT_ACCEPTABLE,
            "not_acceptable",
            "Client must accept application/json",
        )
    elif need_sse and (not has_sse):
        raise_api_error(
            request,
            status.HTTP_406_NOT_ACCEPTABLE,
            "not_acceptable",
            "Client must accept text/event-stream",
        )


def resolve_streamable_http_post_response_mode_or_raise(
    request: Request,
    *,
    need_json: bool = False,
    need_sse: bool = False,
    allow_any: bool = False,
) -> str:
    require_accept(request, need_json=need_json, need_sse=need_sse, allow_any=allow_any)
    accept_header = request.headers.get("accept", "*/*")
    mode = resolve_streamable_http_post_response_mode(accept_header)
    if mode in ("json", "sse"):
        return mode
    raise_api_error(
        request,
        status.HTTP_406_NOT_ACCEPTABLE,
        "not_acceptable",
        "Accept header must include application/json or text/event-stream",
    )


def parse_protocol_version_or_raise(request: Request, *, detailed_error: bool = False) -> str:
    protocol_version_header = request.headers.get(MCP_PROTOCOL_VERSION_HEADER)
    if not protocol_version_header:
        raise_bad_request(
            request,
            "MCP-Protocol-Version header is required",
            error_type="missing_protocol_version",
        )
    version_valid, protocol_version = validate_protocol_version(protocol_version_header)
    if not version_valid:
        if detailed_error:
            supported = ", ".join(SUPPORTED_PROTOCOL_VERSIONS)
            raise_bad_request(
                request,
                f"Unsupported protocol version: {protocol_version}. Supported: {supported}",
                error_type="invalid_protocol_version",
            )
        else:
            raise_bad_request(
                request,
                "Unsupported protocol version",
                error_type="invalid_protocol_version",
            )
    return protocol_version


def resolve_session_id_for_mode(
    request: Request,
    mcp_server_instance: MCPServerProtocol,
    *,
    is_initialize: bool,
    require_header_after_initialize: bool = False,
) -> str:
    session_id_header = request.headers.get(MCP_SESSION_ID_HEADER)
    if is_initialize:
        if session_id_header:
            validate_session_id_or_raise(request, session_id_header)
            return session_id_header
        return mcp_server_instance.session.generate_session_id()
    if session_id_header:
        validate_session_id_or_raise(request, session_id_header)
        return session_id_header
    if require_header_after_initialize:
        return raise_bad_request(
            request,
            "MCP-Session-Id header is required for streamable HTTP requests after initialize",
            error_type="missing_session_id",
        )
    return raise_bad_request(
        request,
        "MCP-Session-Id header is required",
        error_type="missing_session_id",
    )
