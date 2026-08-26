"""SoAI - MCP remote OAuth callback operations [backend/mcp/remote/service_oauth_callback_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.external_accounts.oauth_updates import build_oauth_token_updates
from core.external_accounts.state import parse_scope_text, resolve_oauth_grant_status
from core.oauth.configured_clients import (
    build_configured_auth_server,
    build_configured_client_credentials,
)
from core.oauth.flows import exchange_authorization_code_for_tokens
from core.oauth.http_client_adapter import OAuthHTTPClientAdapter
from core.oauth.state_tokens import (
    OAUTH_STATE_TOKEN_TYPE_MCP_SERVER,
    decode_wrapped_oauth_flow_state,
)
from core.oauth.types import (
    OAuthError,
    OAuthErrorCode,
)
from core.oauth.url_policy import create_oauth_runtime_url_validator
from core.security.secret_crypto import decrypt_optional_secret
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from mcp.remote.config_coercion import mcp_server_config_from_db_row
from mcp.remote.internal_protocols import MCPRemoteOAuthOperationsSurface

__all__ = ("complete_oauth_callback_method",)


async def complete_oauth_callback_method(
    self: MCPRemoteOAuthOperationsSurface,
    *,
    code: str,
    state_token: str,
    user_id: int,
) -> JSONDict:
    flow_state = decode_wrapped_oauth_flow_state(
        self.fernet,
        token=state_token,
        expected_token_type=OAUTH_STATE_TOKEN_TYPE_MCP_SERVER,
        ttl_ms=int(self.oauth_state_token_ttl_ms),
        now_ms=epoch_ms(),
    )
    if flow_state.user_id != int(user_id):
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state user mismatch.")
    server_row = await self.db_mcp.get_mcp_server(flow_state.server_id, decrypt_key=True)
    if server_row is None:
        raise ValidationError("MCP server not found.")
    config = mcp_server_config_from_db_row(server_row)
    token_endpoint = config.oauth_token_endpoint
    auth_endpoint = config.oauth_authorization_endpoint
    issuer_value = config.oauth_auth_server_issuer
    client_id_value = config.oauth_client_id
    token_method_value = config.oauth_token_endpoint_auth_method
    if (
        token_endpoint is None
        or auth_endpoint is None
        or issuer_value is None
        or client_id_value is None
        or token_method_value is None
    ):
        raise ValidationError("OAuth metadata not configured.")
    client_secret = decrypt_optional_secret(
        self.fernet,
        config.oauth_client_secret_encrypted,
        label="mcp oauth_client_secret",
    )
    oauth_http = OAuthHTTPClientAdapter(self.http_client)

    validate_url = create_oauth_runtime_url_validator(self.runtime_flags)

    auth_server = build_configured_auth_server(
        issuer=issuer_value,
        authorization_endpoint=auth_endpoint,
        token_endpoint=token_endpoint,
        registration_endpoint=None,
    )
    client_credentials = build_configured_client_credentials(
        client_id=client_id_value,
        client_secret=client_secret,
        token_endpoint_auth_method=token_method_value,
    )
    tokens = await exchange_authorization_code_for_tokens(
        oauth_http,
        auth_server=auth_server,
        client=client_credentials,
        code=code,
        redirect_uri=flow_state.redirect_uri,
        code_verifier=flow_state.code_verifier,
        resource=flow_state.resource,
        validate_url=validate_url,
        now_ms=epoch_ms,
    )
    granted_scopes = parse_scope_text(tokens.scope) or flow_state.scopes
    required_scopes = tuple(config.oauth_required_scopes or ())
    oauth_status = resolve_oauth_grant_status(
        required_scopes=required_scopes,
        granted_scopes=granted_scopes,
    )
    await self.db_mcp.update_mcp_server(
        flow_state.server_id,
        {
            "auth_type": "oauth",
            **build_oauth_token_updates(
                oauth_status=oauth_status,
                tokens=tokens,
                retained_refresh_token=None,
            ),
            "oauth_scopes": list(granted_scopes) if granted_scopes else None,
            "oauth_required_scopes": (
                list(required_scopes)
                if oauth_status == "insufficient_scope" and required_scopes
                else None
            ),
        },
    )
    if oauth_status != "ready":
        return {
            "ok": False,
            "server_id": flow_state.server_id,
            "oauth_status": oauth_status,
        }
    connect_ok = await self.connect_to_server_by_id(flow_state.server_id)
    return {
        "ok": bool(connect_ok),
        "server_id": flow_state.server_id,
        "oauth_status": "ready" if connect_ok else "error",
    }
