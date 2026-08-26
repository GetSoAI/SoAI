"""SoAI - MCP remote host-mode auth retry handling [backend/mcp/remote/host_mode_auth_retry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, NoReturn

import httpx2

from core.mcp.protocols_storage import DatabaseMCPProtocol
from core.oauth.types import OAuthError
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.types.json import JSONDict, JSONValue
from mcp.protocol.connection_request_state import cancel_all_pending_requests
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.streamable_http_response import (
    MCPStreamAuthorizationError,
    MCPStreamInsufficientScopeError,
)
from mcp.protocol.types import MCPServerStatus
from mcp.remote.oauth_auth_errors import (
    extract_mcp_auth_error_details,
    persist_mcp_oauth_auth_error,
)
from mcp.remote.oauth_refresh import refresh_connection_oauth_token

if TYPE_CHECKING:
    type CleanupConnectionResources = Callable[[MCPServerConnection], Awaitable[None]]
    type DecryptSecret = Callable[[str], str | None]
    type HostModeMessageSender = Callable[[JSONDict], Awaitable[None]]
    type HostModeRequestSender = Callable[[str, JSONDict], Awaitable[JSONValue | None]]

__all__ = (
    "send_host_mode_message_with_auth_retry",
    "send_host_mode_request_with_auth_retry",
)


async def _handle_auth_failure(
    *,
    connection: MCPServerConnection,
    exception: BaseException,
    status_code: int,
    www_authenticate: str | None,
    cleanup_connection_resources: CleanupConnectionResources,
    db_mcp: DatabaseMCPProtocol,
) -> None:
    async with connection.request_state.lock:
        connection.task_state.user_disconnected = True
        connection.status = MCPServerStatus.AUTH_REQUIRED
        connection.last_error = str(exception)
    await cleanup_connection_resources(connection)
    await cancel_all_pending_requests(connection.request_state)
    await persist_mcp_oauth_auth_error(
        db_mcp,
        server_id=connection.config.id,
        status_code=status_code,
        www_authenticate=www_authenticate,
        auth_type=connection.config.auth_type,
    )


async def _refresh_connection_after_auth_failure(
    *,
    connection: MCPServerConnection,
    db_mcp: DatabaseMCPProtocol,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    decrypt_secret: DecryptSecret,
) -> bool:
    if connection.config.auth_type != "oauth":
        return False
    if not connection.config.oauth_refresh_token_encrypted:
        return False
    async with connection.task_state.oauth_refresh_lock:
        await refresh_connection_oauth_token(
            connection=connection,
            db_mcp=db_mcp,
            http_client=http_client,
            runtime_flags=runtime_flags,
            decrypt_secret=decrypt_secret,
        )
    return True


async def _record_auth_failure_and_raise(
    *,
    connection: MCPServerConnection,
    exception: MCPStreamAuthorizationError | MCPStreamInsufficientScopeError,
    default_status: int,
    cleanup_connection_resources: CleanupConnectionResources,
    db_mcp: DatabaseMCPProtocol,
) -> NoReturn:
    status_code, www_authenticate = extract_mcp_auth_error_details(
        exception.details,
        default_status=default_status,
    )
    await _handle_auth_failure(
        connection=connection,
        exception=exception,
        status_code=status_code,
        www_authenticate=www_authenticate,
        cleanup_connection_resources=cleanup_connection_resources,
        db_mcp=db_mcp,
    )
    raise exception


async def _record_refresh_failure_and_raise(
    *,
    connection: MCPServerConnection,
    refresh_exception: OAuthError,
    original_exception: MCPStreamAuthorizationError | MCPStreamInsufficientScopeError,
    default_status: int,
    cleanup_connection_resources: CleanupConnectionResources,
    db_mcp: DatabaseMCPProtocol,
) -> NoReturn:
    status_code, www_authenticate = extract_mcp_auth_error_details(
        original_exception.details,
        default_status=default_status,
    )
    await _handle_auth_failure(
        connection=connection,
        exception=refresh_exception,
        status_code=status_code,
        www_authenticate=www_authenticate,
        cleanup_connection_resources=cleanup_connection_resources,
        db_mcp=db_mcp,
    )
    raise original_exception


async def send_host_mode_message_with_auth_retry(
    *,
    connection: MCPServerConnection,
    message: JSONDict,
    db_mcp: DatabaseMCPProtocol,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    decrypt_secret: DecryptSecret,
    cleanup_connection_resources: CleanupConnectionResources,
    send_message: HostModeMessageSender,
) -> None:
    try:
        await send_message(message)
        return
    except MCPStreamAuthorizationError as exception:
        original_exception = exception
        try:
            did_refresh = await _refresh_connection_after_auth_failure(
                connection=connection,
                db_mcp=db_mcp,
                http_client=http_client,
                runtime_flags=runtime_flags,
                decrypt_secret=decrypt_secret,
            )
            if did_refresh:
                await send_message(message)
                return
        except MCPStreamAuthorizationError as retry_exception:
            original_exception = retry_exception
        except MCPStreamInsufficientScopeError as retry_exception:
            await _record_auth_failure_and_raise(
                connection=connection,
                exception=retry_exception,
                default_status=403,
                cleanup_connection_resources=cleanup_connection_resources,
                db_mcp=db_mcp,
            )
        except OAuthError as refresh_exception:
            await _record_refresh_failure_and_raise(
                connection=connection,
                refresh_exception=refresh_exception,
                original_exception=original_exception,
                default_status=401,
                cleanup_connection_resources=cleanup_connection_resources,
                db_mcp=db_mcp,
            )
        await _record_auth_failure_and_raise(
            connection=connection,
            exception=original_exception,
            default_status=401,
            cleanup_connection_resources=cleanup_connection_resources,
            db_mcp=db_mcp,
        )
    except MCPStreamInsufficientScopeError as exception:
        await _record_auth_failure_and_raise(
            connection=connection,
            exception=exception,
            default_status=403,
            cleanup_connection_resources=cleanup_connection_resources,
            db_mcp=db_mcp,
        )


async def send_host_mode_request_with_auth_retry(
    *,
    connection: MCPServerConnection,
    method: str,
    parameters: JSONDict,
    db_mcp: DatabaseMCPProtocol,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    decrypt_secret: DecryptSecret,
    cleanup_connection_resources: CleanupConnectionResources,
    send_request: HostModeRequestSender,
) -> JSONValue | None:
    try:
        return await send_request(method, parameters)
    except MCPStreamAuthorizationError as exception:
        original_exception = exception
        try:
            did_refresh = await _refresh_connection_after_auth_failure(
                connection=connection,
                db_mcp=db_mcp,
                http_client=http_client,
                runtime_flags=runtime_flags,
                decrypt_secret=decrypt_secret,
            )
            if did_refresh:
                return await send_request(method, parameters)
        except MCPStreamAuthorizationError as retry_exception:
            original_exception = retry_exception
        except MCPStreamInsufficientScopeError as retry_exception:
            await _record_auth_failure_and_raise(
                connection=connection,
                exception=retry_exception,
                default_status=403,
                cleanup_connection_resources=cleanup_connection_resources,
                db_mcp=db_mcp,
            )
        except OAuthError as refresh_exception:
            await _record_refresh_failure_and_raise(
                connection=connection,
                refresh_exception=refresh_exception,
                original_exception=original_exception,
                default_status=401,
                cleanup_connection_resources=cleanup_connection_resources,
                db_mcp=db_mcp,
            )
        await _record_auth_failure_and_raise(
            connection=connection,
            exception=original_exception,
            default_status=401,
            cleanup_connection_resources=cleanup_connection_resources,
            db_mcp=db_mcp,
        )
    except MCPStreamInsufficientScopeError as exception:
        await _record_auth_failure_and_raise(
            connection=connection,
            exception=exception,
            default_status=403,
            cleanup_connection_resources=cleanup_connection_resources,
            db_mcp=db_mcp,
        )
