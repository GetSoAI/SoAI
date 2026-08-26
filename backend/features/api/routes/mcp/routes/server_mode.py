"""SoAI - MCP server-mode Streamable HTTP endpoints [backend/features/api/routes/mcp/routes/server_mode.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request, Response, status
from fastapi.responses import StreamingResponse

from core.errors.external_service_exception import MCPError
from core.mcp.error_mapping import project_mcp_error_fields
from core.mcp.http_negotiation import (
    MCP_STREAMABLE_HTTP_SSE_MEDIA_TYPE,
    build_mcp_streamable_http_headers,
)
from core.mcp.jsonrpc_messages import classify_jsonrpc_message
from core.mcp.mcp_2025_11_25 import MCP_SESSION_ID_HEADER
from core.mcp.protocols_main import MCPServerProtocol
from core.state.access import AccessAction
from features.api.routes.mcp.routes.origin_validation import (
    resolve_current_user_id,
    validate_mcp_origin,
)
from features.api.routes.mcp.routes.server_mode_jsonrpc import (
    create_jsonrpc_error_response,
    read_jsonrpc_body_or_error_response,
)
from features.api.routes.mcp.routes.server_mode_protocol import (
    resolve_streamable_http_post_protocol_version,
)
from features.api.routes.mcp.routes.server_mode_session import (
    ensure_client_session_error,
    ensure_client_session_or_raise,
    require_existing_session,
    require_session_owner_or_raise,
)
from features.api.routes.mcp.routes.server_mode_validation import (
    require_accept,
    require_content_type_json,
    require_mcp_server_mode,
    resolve_session_id_for_mode,
    resolve_streamable_http_post_response_mode_or_raise,
    validate_session_id_or_raise,
)
from features.api.routes.mcp.routes.server_streaming import (
    STREAMABLE_HTTP_SSE_PREAMBLE,
    mcp_notification_stream,
    streamable_http_single_message_stream,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import get_current_user_optional, resolve_api_context
from features.api.runtime.current_user import get_current_user
from features.api.runtime.errors import (
    raise_bad_request,
    raise_server_error,
)
from features.api.runtime.response_body import create_json_body_response
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.user_types import CurrentUser

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.mcp_streamable_http.get(
        "/whoami",
        dependencies=require_action_dependencies(AccessAction.MCP_USE),
    )
    async def mcp_whoami(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
    ) -> Response:
        username = current_user.get("username")
        if not isinstance(username, str) or not username:
            raise_server_error(
                request,
                "User record is missing username.",
            )
        return create_json_body_response(
            content={"user_id": current_user["id"], "username": username},
        )

    @routers.mcp_streamable_http.post(
        "",
        dependencies=require_action_dependencies(AccessAction.MCP_USE),
    )
    async def mcp_server_streamable_http_endpoint(
        request: Request,
        mcp_server_instance: MCPServerProtocol = Depends(validate_mcp_origin),
        current_user: CurrentUser | None = Depends(get_current_user_optional),
    ) -> Response:
        require_mcp_server_mode(request, mcp_server_instance)
        require_content_type_json(request)
        body_or_error_response = await read_jsonrpc_body_or_error_response(request)
        if isinstance(body_or_error_response, Response):
            return body_or_error_response
        body = body_or_error_response
        classification = classify_jsonrpc_message(body)
        if classification.type == "invalid":
            return create_jsonrpc_error_response(
                classification.rpc_id,
                -32600,
                "Invalid JSON-RPC message.",
            )
        is_initialize = classification.type == "request" and classification.method == "initialize"
        session_id = resolve_session_id_for_mode(
            request,
            mcp_server_instance,
            is_initialize=is_initialize,
            require_header_after_initialize=True,
        )
        if not is_initialize:
            await require_existing_session(request, mcp_server_instance, session_id)
        if is_initialize:
            require_accept(request, need_json=True)
            mode = "json"
        else:
            mode = resolve_streamable_http_post_response_mode_or_raise(
                request,
                need_json=True,
                need_sse=True,
                allow_any=True,
            )
        protocol_version = resolve_streamable_http_post_protocol_version(
            request,
            body,
            is_initialize=is_initialize,
            mcp_server_instance=mcp_server_instance,
            session_id=session_id,
        )
        user_id = resolve_current_user_id(current_user)
        response_headers = build_mcp_streamable_http_headers(session_id)
        client_session_error = await ensure_client_session_error(
            request,
            mcp_server_instance,
            session_id,
            protocol_version,
            user_id,
            create_if_missing=is_initialize,
        )
        if client_session_error is not None:
            return create_jsonrpc_error_response(
                classification.rpc_id,
                client_session_error.rpc_code,
                client_session_error.message,
                client_session_error.rpc_data,
                headers=response_headers,
            )
        if classification.type == "response":
            return Response(status_code=status.HTTP_202_ACCEPTED, headers=response_headers)
        try:
            response_data = await mcp_server_instance.handle_mcp_request(
                body,
                session_id,
                session_id,
                protocol_version,
            )
        except MCPError as exception:
            public_message, public_data = project_mcp_error_fields(
                exception.rpc_code,
                exception.message,
                exception.rpc_data,
            )
            return create_jsonrpc_error_response(
                classification.rpc_id,
                exception.rpc_code,
                public_message,
                public_data,
                headers=response_headers,
            )
        if classification.type == "notification":
            return Response(status_code=status.HTTP_202_ACCEPTED, headers=response_headers)
        if not isinstance(response_data, dict):
            raise_server_error(
                request,
                "MCP server returned an invalid JSON-RPC response.",
            )
        if mode == "json":
            return create_json_body_response(
                content=response_data,
                status_code=status.HTTP_200_OK,
                headers=response_headers,
            )
        return StreamingResponse(
            streamable_http_single_message_stream(mcp_server_instance, session_id, response_data),
            media_type=MCP_STREAMABLE_HTTP_SSE_MEDIA_TYPE,
            status_code=status.HTTP_200_OK,
            headers=build_mcp_streamable_http_headers(session_id, sse=True),
        )

    @routers.mcp_streamable_http.get(
        "",
        dependencies=require_action_dependencies(AccessAction.MCP_USE),
    )
    async def mcp_server_streamable_http_stream(
        request: Request,
        mcp_server_instance: MCPServerProtocol = Depends(validate_mcp_origin),
        current_user: CurrentUser | None = Depends(get_current_user_optional),
    ) -> StreamingResponse:
        api_context = resolve_api_context(request)
        require_mcp_server_mode(request, mcp_server_instance)
        require_accept(request, need_sse=True)
        session_id = request.headers.get(MCP_SESSION_ID_HEADER)
        if not session_id:
            raise_bad_request(
                request,
                "MCP-Session-Id header is required. Initialize the session first with POST /mcp using the 'initialize' method.",
                error_type="missing_session_id",
            )
        validate_session_id_or_raise(request, session_id)
        await require_existing_session(request, mcp_server_instance, session_id)
        protocol_version = resolve_streamable_http_post_protocol_version(
            request,
            {},
            is_initialize=False,
            mcp_server_instance=mcp_server_instance,
            session_id=session_id,
        )
        user_id = resolve_current_user_id(current_user)
        await ensure_client_session_or_raise(
            request,
            mcp_server_instance,
            session_id,
            protocol_version,
            user_id,
            create_if_missing=False,
        )
        await mcp_server_instance.streaming.sync_sse_event_counter_from_last_event_id(
            session_id,
            request.headers.get("last-event-id"),
        )
        return StreamingResponse(
            mcp_notification_stream(
                mcp_server_instance,
                session_id,
                STREAMABLE_HTTP_SSE_PREAMBLE,
                request.headers.get("last-event-id"),
                shutdown_events=(api_context.dependencies.shutdown_event,),
            ),
            media_type=MCP_STREAMABLE_HTTP_SSE_MEDIA_TYPE,
            headers=build_mcp_streamable_http_headers(session_id, sse=True),
        )

    @routers.mcp_streamable_http.delete(
        "",
        status_code=204,
        dependencies=require_action_dependencies(AccessAction.MCP_USE),
    )
    async def mcp_server_streamable_http_delete(
        request: Request,
        mcp_server_instance: MCPServerProtocol = Depends(validate_mcp_origin),
        current_user: CurrentUser | None = Depends(get_current_user_optional),
    ) -> Response:
        require_mcp_server_mode(request, mcp_server_instance)
        session_id = request.headers.get(MCP_SESSION_ID_HEADER)
        if not session_id:
            raise_bad_request(
                request,
                "MCP-Session-Id header is required to terminate the session",
                error_type="missing_session_id",
            )
        validate_session_id_or_raise(request, session_id)
        await require_existing_session(request, mcp_server_instance, session_id)
        user_id = resolve_current_user_id(current_user)
        require_session_owner_or_raise(request, mcp_server_instance, session_id, user_id)
        await mcp_server_instance.session.close_client_session(session_id)
        return create_no_content_response()
