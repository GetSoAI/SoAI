"""SoAI - MCP remote OAuth token refresh support [backend/mcp/remote/oauth_refresh.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx2

from core.external_accounts.oauth_updates import build_oauth_token_updates
from core.external_accounts.state import parse_scope_text, resolve_oauth_grant_status
from core.mcp.protocols_storage import DatabaseMCPProtocol
from core.oauth.configured_clients import (
    build_configured_auth_server,
    build_configured_client_credentials,
    require_configured_oauth_text,
)
from core.oauth.flows import oauth_token_expires_within_skew, refresh_access_token
from core.oauth.http_client_adapter import OAuthHTTPClientAdapter
from core.oauth.management_urls import require_https_url
from core.oauth.types import OAuthError, OAuthErrorCode
from core.oauth.url_policy import create_oauth_runtime_url_validator
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.timing.epoch import epoch_ms
from mcp.protocol.connection_state import MCPServerConnection
from mcp.remote.config_coercion import mcp_server_config_from_db_row

if TYPE_CHECKING:
    type DecryptSecret = Callable[[str], str | None]

__all__ = ("maybe_refresh_connection_oauth_token",)


async def maybe_refresh_connection_oauth_token(
    *,
    connection: MCPServerConnection,
    db_mcp: DatabaseMCPProtocol,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    decrypt_secret: DecryptSecret,
    refresh_skew_ms: int,
) -> None:
    config = connection.config
    if config.auth_type != "oauth":
        return
    if not config.oauth_refresh_token_encrypted:
        return
    if not oauth_token_expires_within_skew(
        config.oauth_expires_at_ms,
        now_ms=epoch_ms(),
        skew_ms=refresh_skew_ms,
    ):
        return
    async with connection.task_state.oauth_refresh_lock:
        updated_config = connection.config
        if updated_config.auth_type != "oauth":
            return
        if not updated_config.oauth_refresh_token_encrypted:
            return
        if not oauth_token_expires_within_skew(
            updated_config.oauth_expires_at_ms,
            now_ms=epoch_ms(),
            skew_ms=refresh_skew_ms,
        ):
            return
        await refresh_connection_oauth_token(
            connection=connection,
            db_mcp=db_mcp,
            http_client=http_client,
            runtime_flags=runtime_flags,
            decrypt_secret=decrypt_secret,
        )


async def refresh_connection_oauth_token(
    *,
    connection: MCPServerConnection,
    db_mcp: DatabaseMCPProtocol,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    decrypt_secret: DecryptSecret,
) -> None:
    config = connection.config
    if config.auth_type != "oauth":
        return
    issuer = require_configured_oauth_text(
        config.oauth_auth_server_issuer,
        "oauth_auth_server_issuer",
    )
    auth_endpoint = require_configured_oauth_text(
        config.oauth_authorization_endpoint,
        "oauth_authorization_endpoint",
    )
    token_endpoint = require_configured_oauth_text(
        config.oauth_token_endpoint,
        "oauth_token_endpoint",
    )
    require_https_url(issuer, "oauth_auth_server_issuer")
    require_https_url(auth_endpoint, "oauth_authorization_endpoint")
    require_https_url(token_endpoint, "oauth_token_endpoint")
    client_id = require_configured_oauth_text(config.oauth_client_id, "oauth_client_id")
    token_method = config.oauth_token_endpoint_auth_method or "none"
    refresh_token = decrypt_secret(config.oauth_refresh_token_encrypted or "")
    if not refresh_token:
        raise OAuthError(OAuthErrorCode.TOKEN_REFRESH_FAILED, "Missing refresh token.")
    client_secret = (
        decrypt_secret(config.oauth_client_secret_encrypted)
        if config.oauth_client_secret_encrypted
        else None
    )
    oauth_http = OAuthHTTPClientAdapter(http_client)

    validate_url = create_oauth_runtime_url_validator(runtime_flags)

    auth_server = build_configured_auth_server(
        issuer=issuer,
        authorization_endpoint=auth_endpoint,
        token_endpoint=token_endpoint,
        registration_endpoint=config.oauth_registration_endpoint,
    )
    client_credentials = build_configured_client_credentials(
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint_auth_method=token_method,
    )
    tokens = await refresh_access_token(
        oauth_http,
        auth_server=auth_server,
        client=client_credentials,
        refresh_token=refresh_token,
        resource=config.endpoint,
        validate_url=validate_url,
        now_ms=epoch_ms,
    )
    granted_scopes = parse_scope_text(tokens.scope) or tuple(config.oauth_scopes or ())
    oauth_status = resolve_oauth_grant_status(
        required_scopes=tuple(config.oauth_required_scopes or ()),
        granted_scopes=granted_scopes,
    )
    await db_mcp.update_mcp_server(
        config.id,
        {
            **build_oauth_token_updates(
                oauth_status=oauth_status,
                tokens=tokens,
                retained_refresh_token=refresh_token,
            ),
            "oauth_scopes": list(granted_scopes) if granted_scopes else None,
            "oauth_required_scopes": (
                list(config.oauth_required_scopes)
                if oauth_status == "insufficient_scope" and config.oauth_required_scopes
                else None
            ),
        },
    )
    refreshed_row = await db_mcp.get_mcp_server(config.id, decrypt_key=True)
    if refreshed_row is None:
        return
    connection.config = mcp_server_config_from_db_row(refreshed_row)
