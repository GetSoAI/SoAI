"""SoAI - MCP remote OAuth authorization start operations [backend/mcp/remote/service_oauth_authorization_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import httpx2

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.external_accounts.oauth_updates import build_oauth_connection_updates
from core.external_accounts.state import parse_scope_text
from core.logging.trace import get_logger
from core.mcp.protocol_versions import MCP_PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS
from core.oauth.discovery import (
    discover_authorization_server_metadata,
    discover_protected_resource_metadata,
)
from core.oauth.flows import build_authorization_url
from core.oauth.http_client_adapter import OAuthHTTPClientAdapter
from core.oauth.management_urls import (
    resolve_mcp_oauth_callback_url,
    resolve_mcp_public_client_metadata_url,
)
from core.oauth.pkce import generate_code_verifier
from core.oauth.registration import resolve_client_credentials
from core.oauth.state_tokens import (
    OAUTH_STATE_TOKEN_TYPE_MCP_SERVER,
    encode_wrapped_oauth_flow_state,
)
from core.oauth.types import OAuthError, OAuthFlowState
from core.oauth.url_policy import create_oauth_runtime_url_validator
from core.oauth.www_authenticate import parse_www_authenticate_bearer_challenge
from core.runtime.network_policy import validate_local_only_url
from core.security.secret_crypto import decrypt_optional_secret
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from mcp.protocol.http_headers import build_mcp_http_headers
from mcp.protocol.jsonrpc import build_core_app_info, build_jsonrpc_request
from mcp.remote.config_coercion import mcp_server_config_from_db_row
from mcp.remote.internal_protocols import MCPRemoteOAuthOperationsSurface

__all__ = (
    "connect_to_server_by_id_method",
    "start_oauth_authorization_method",
)

LOGGER_NAME = "SoAI.mcp.remote.service_oauth_authorization_operations"
OPERATION_OAUTH_INITIALIZE = "mcp.remote.oauth.initialize"


async def connect_to_server_by_id_method(
    self: MCPRemoteOAuthOperationsSurface,
    server_id: str,
) -> bool:
    server_row = await self.db_mcp.get_mcp_server(server_id, decrypt_key=True)
    if server_row is None:
        raise ValidationError(f"MCP server '{server_id}' not found.")
    config = mcp_server_config_from_db_row(server_row)
    return await self.connection_manager.connect_to_server(config)


async def start_oauth_authorization_method(
    self: MCPRemoteOAuthOperationsSurface,
    *,
    server_id: str,
    user_id: int,
) -> JSONDict:
    server_row = await self.db_mcp.get_mcp_server(server_id, decrypt_key=True)
    if server_row is None:
        raise ValidationError(f"MCP server '{server_id}' not found.")
    config = mcp_server_config_from_db_row(server_row)
    if str(config.transport_type) != "streamable_http":
        raise ValidationError("OAuth is only supported for Streamable HTTP MCP servers.")
    configured_base_url = str(self.public_origin or "")
    callback_url = resolve_mcp_oauth_callback_url(
        configured_base_url=configured_base_url,
    )
    await validate_local_only_url(
        self.runtime_flags,
        config.endpoint,
        source="MCP OAuth start",
    )
    include_auth = bool(config.auth_type == "oauth" and config.oauth_access_token_encrypted)
    base_headers = build_mcp_http_headers(
        config,
        protocol_version=MCP_PROTOCOL_VERSION,
        decrypt_secret=self.decrypt_mcp_api_key if include_auth else (lambda _value: None),
    )
    params: JSONDict = {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "supportedProtocolVersions": list(SUPPORTED_PROTOCOL_VERSIONS),
        "capabilities": self.build_client_capabilities(),
        "clientInfo": build_core_app_info(),
    }
    message = build_jsonrpc_request(1, "initialize", params)
    try:
        response = await self.http_client.post(
            config.endpoint,
            json=message,
            headers={
                **base_headers,
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            timeout=config.timeout_sec,
        )
    except httpx2.RequestError as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="MCP OAuth initialization request failed.",
            operation=OPERATION_OAUTH_INITIALIZE,
            details={"server_id": server_id},
            level="warning",
        )
        return {"status": "error", "error": "MCP server request failed."}

    if response.status_code in (200, 202):
        await connect_to_server_by_id_method(self, server_id)
        return {"status": "not_required"}

    if response.status_code not in (401, 403):
        return {"status": "error", "error": f"initialize returned HTTP {response.status_code}"}

    challenge = parse_www_authenticate_bearer_challenge(response.headers.get("WWW-Authenticate"))
    if challenge is None:
        return {"status": "error", "error": "Missing OAuth WWW-Authenticate challenge."}

    oauth_http = OAuthHTTPClientAdapter(self.http_client)

    validate_url = create_oauth_runtime_url_validator(self.runtime_flags)

    protected_resource, resource_metadata_url = await discover_protected_resource_metadata(
        oauth_http,
        resource=config.endpoint,
        challenge=challenge,
        validate_url=validate_url,
    )
    issuer = protected_resource.authorization_servers[0]
    auth_server = await discover_authorization_server_metadata(
        oauth_http,
        issuer=issuer,
        validate_url=validate_url,
    )
    challenge_scopes = parse_scope_text(challenge.scope)
    scopes = challenge_scopes
    if not scopes and protected_resource.scopes_supported is not None:
        scopes = tuple(parse_scope_text(" ".join(protected_resource.scopes_supported)))

    prereg_client_id = config.oauth_client_id
    prereg_secret = decrypt_optional_secret(
        self.fernet,
        config.oauth_client_secret_encrypted,
        label="mcp oauth_client_secret",
    )

    public_metadata_url = (
        resolve_mcp_public_client_metadata_url(configured_base_url=configured_base_url)
        if auth_server.client_id_metadata_document_supported
        else None
    )
    try:
        client_credentials = await resolve_client_credentials(
            oauth_http,
            auth_server=auth_server,
            redirect_uri=callback_url,
            public_client_metadata_url=public_metadata_url,
            preregistered_client_id=prereg_client_id,
            preregistered_client_secret=prereg_secret,
            validate_url=validate_url,
        )
    except OAuthError as exception:
        if exception.code.value == "manual_client_required":
            return {"status": "manual_required", "required_fields": ["client_id", "client_secret?"]}
        raise
    verifier = generate_code_verifier()
    state_token = encode_wrapped_oauth_flow_state(
        self.fernet,
        state=OAuthFlowState(
            server_id=server_id,
            user_id=int(user_id),
            code_verifier=verifier,
            resource=config.endpoint,
            redirect_uri=callback_url,
            scopes=scopes,
            created_at_ms=epoch_ms(),
        ),
        token_type=OAUTH_STATE_TOKEN_TYPE_MCP_SERVER,
    )
    redirect_url = build_authorization_url(
        auth_server=auth_server,
        client_id=client_credentials.client_id,
        redirect_uri=callback_url,
        state=state_token,
        code_verifier=verifier,
        resource=config.endpoint,
        scopes=scopes,
    )
    await self.db_mcp.update_mcp_server(
        server_id,
        {
            "auth_type": "oauth",
            **build_oauth_connection_updates(
                client_credentials=client_credentials,
                auth_server=auth_server,
                resource_metadata_url=resource_metadata_url,
            ),
            "oauth_scopes": list(scopes) if scopes else None,
            "oauth_required_scopes": (
                list(challenge_scopes)
                if response.status_code == 403
                and challenge.error == "insufficient_scope"
                and challenge_scopes
                else None
            ),
        },
    )
    return {"status": "redirect", "redirect_url": redirect_url}
