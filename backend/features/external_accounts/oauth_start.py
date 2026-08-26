"""SoAI - External account OAuth start flow [backend/features/external_accounts/oauth_start.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.external_accounts.oauth_config import (
    read_optional_account_text,
    resolve_account_issuer,
    resolve_account_resource,
    resolve_account_scopes,
)
from core.external_accounts.oauth_updates import build_oauth_connection_updates
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
    OAUTH_STATE_TOKEN_TYPE_EXTERNAL_ACCOUNT,
    encode_wrapped_oauth_flow_state,
)
from core.oauth.types import OAuthFlowState
from core.oauth.url_policy import create_oauth_runtime_url_validator
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.external_accounts.internal_protocols import (
    ExternalAccountsOAuthServiceProtocol,
)
from features.external_accounts.oauth_account_loading import (
    locked_oauth2_external_account,
)

__all__ = ("start_oauth_method",)


async def start_oauth_method(
    self: ExternalAccountsOAuthServiceProtocol,
    *,
    user_id: int,
    external_account_id: str,
    resource: str,
) -> JSONDict:
    async with locked_oauth2_external_account(
        self,
        user_id=user_id,
        external_account_id=external_account_id,
    ) as account:
        configured_base_url = str(self.public_origin or "")
        callback_url = resolve_mcp_oauth_callback_url(
            configured_base_url=configured_base_url,
        )
        resource_value = resolve_account_resource(account, resource)
        oauth_http = OAuthHTTPClientAdapter(self.http_client)

        validate_url = create_oauth_runtime_url_validator(self.runtime_flags)

        protected_resource, resource_metadata_url = await discover_protected_resource_metadata(
            oauth_http,
            resource=resource_value,
            challenge=None,
            validate_url=validate_url,
        )
        auth_server = await discover_authorization_server_metadata(
            oauth_http,
            issuer=resolve_account_issuer(account, protected_resource),
            validate_url=validate_url,
        )
        public_metadata_url = resolve_mcp_public_client_metadata_url(
            configured_base_url=configured_base_url,
        )
        client_credentials = await resolve_client_credentials(
            oauth_http,
            auth_server=auth_server,
            redirect_uri=callback_url,
            public_client_metadata_url=public_metadata_url,
            preregistered_client_id=read_optional_account_text(account, "oauth_client_id"),
            preregistered_client_secret=read_optional_account_text(
                account,
                "oauth_client_secret",
            ),
            validate_url=validate_url,
        )
        scopes = resolve_account_scopes(account, protected_resource)
        verifier = generate_code_verifier()
        state_token = encode_wrapped_oauth_flow_state(
            self.database_external_accounts.fernet,
            state=OAuthFlowState(
                server_id=external_account_id,
                user_id=int(user_id),
                code_verifier=verifier,
                resource=resource_value,
                redirect_uri=callback_url,
                scopes=scopes,
                created_at_ms=epoch_ms(),
            ),
            token_type=OAUTH_STATE_TOKEN_TYPE_EXTERNAL_ACCOUNT,
        )
        redirect_url = build_authorization_url(
            auth_server=auth_server,
            client_id=client_credentials.client_id,
            redirect_uri=callback_url,
            state=state_token,
            code_verifier=verifier,
            resource=resource_value,
            scopes=scopes,
        )
        updated_account = await self.update_account(
            user_id=user_id,
            external_account_id=external_account_id,
            updates=build_oauth_connection_updates(
                client_credentials=client_credentials,
                auth_server=auth_server,
                resource_metadata_url=resource_metadata_url,
            ),
        )
        if updated_account is None:
            raise ValidationError("External account not found.")
        return {
            "ok": True,
            "external_account_id": external_account_id,
            "oauth_status": "auth_required",
            "redirect_url": redirect_url,
        }
