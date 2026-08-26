"""SoAI - MCP server-mode Streamable HTTP session helpers [backend/features/api/routes/mcp/routes/server_mode_session.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.errors.external_service_exception import MCPError
from core.mcp.protocols_main import MCPServerProtocol
from features.api.routes.mcp.route_errors import raise_mcp_route_error
from features.api.runtime.errors import raise_forbidden, raise_not_found

__all__ = (
    "ensure_client_session",
    "ensure_client_session_error",
    "ensure_client_session_or_raise",
    "require_existing_session",
    "require_session_owner_or_raise",
)


async def require_existing_session(
    request: Request,
    mcp_server_instance: MCPServerProtocol,
    session_id: str,
) -> None:
    if not await mcp_server_instance.session.has_client_session(session_id):
        raise_not_found(
            request,
            "MCP session not found",
            error_type="session_not_found",
        )


async def ensure_client_session(
    request: Request,
    mcp_server_instance: MCPServerProtocol,
    session_id: str,
    protocol_version: str,
    user_id: int = 0,
    create_if_missing: bool = True,
) -> None:
    await mcp_server_instance.session.ensure_client_session(
        session_id,
        protocol_version,
        user_id,
        create_if_missing=create_if_missing,
    )
    if user_id:
        session = mcp_server_instance.session.get_session(session_id)
        if session and session.user_id not in {0, user_id}:
            raise_forbidden(
                request,
                "MCP session is owned by a different user.",
                error_type="forbidden",
            )


async def ensure_client_session_or_raise(
    request: Request,
    mcp_server_instance: MCPServerProtocol,
    session_id: str,
    protocol_version: str,
    user_id: int = 0,
    create_if_missing: bool = True,
) -> None:
    exception = await ensure_client_session_error(
        request,
        mcp_server_instance,
        session_id,
        protocol_version,
        user_id,
        create_if_missing=create_if_missing,
    )
    if exception is not None:
        raise_mcp_route_error(request, exception, error_type="mcp_error")


async def ensure_client_session_error(
    request: Request,
    mcp_server_instance: MCPServerProtocol,
    session_id: str,
    protocol_version: str,
    user_id: int = 0,
    create_if_missing: bool = True,
) -> MCPError | None:
    try:
        await ensure_client_session(
            request,
            mcp_server_instance,
            session_id,
            protocol_version,
            user_id,
            create_if_missing=create_if_missing,
        )
    except MCPError as exception:
        return exception
    return None


def require_session_owner_or_raise(
    request: Request,
    mcp_server_instance: MCPServerProtocol,
    session_id: str,
    current_user_id: int,
) -> None:
    session_user_id = mcp_server_instance.session.get_session_user_id(session_id)
    if current_user_id == 0:
        if session_user_id != 0:
            raise_forbidden(
                request,
                "MCP session is owned by a different user.",
                error_type="forbidden",
            )
        return
    if session_user_id not in {0, current_user_id}:
        raise_forbidden(
            request,
            "MCP session is owned by a different user.",
            error_type="forbidden",
        )
