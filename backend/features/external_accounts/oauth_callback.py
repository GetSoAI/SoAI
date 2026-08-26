"""SoAI - External account OAuth callback operations [backend/features/external_accounts/oauth_callback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.external_accounts.oauth_config import (
    build_account_auth_server,
    build_account_client_credentials,
    resolve_account_oauth_grant_status,
)
from core.external_accounts.oauth_updates import (
    build_oauth_clear_updates,
    build_oauth_token_updates,
)
from core.external_accounts.state import (
    parse_scope_text,
    require_oauth2_account,
)
from core.oauth.flows import exchange_authorization_code_for_tokens
from core.oauth.http_client_adapter import OAuthHTTPClientAdapter
from core.oauth.state_tokens import (
    OAUTH_STATE_TOKEN_TYPE_EXTERNAL_ACCOUNT,
    decode_wrapped_oauth_flow_state,
)
from core.oauth.types import OAuthError, OAuthErrorCode
from core.oauth.url_policy import create_oauth_runtime_url_validator
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from features.external_accounts.account_envelope import (
    resolve_external_account_oauth_status,
)
from features.external_accounts.internal_protocols import (
    ExternalAccountsOAuthServiceProtocol,
)

__all__ = (
    "clear_oauth_method",
    "complete_oauth_callback_method",
    "get_oauth_status_method",
)


async def get_oauth_status_method(
    self: ExternalAccountsOAuthServiceProtocol,
    *,
    user_id: int,
    external_account_id: str,
) -> JSONDict:
    async with self.account_lock(
        user_id=user_id,
        external_account_id=external_account_id,
    ):
        account = await self.get_account(
            user_id,
            external_account_id,
            decrypt_secrets=False,
        )
        if account is None:
            raise ValidationError("External account not found.")
        require_oauth2_account(account)
        expires_at_ms = account.get("oauth_expires_at_ms")
        has_refresh_token = account.get("oauth_has_refresh_token") is True
        oauth_status = resolve_external_account_oauth_status(account)
        return {
            "external_account_id": external_account_id,
            "oauth_status": oauth_status,
            "oauth_expires_at_ms": (int(expires_at_ms) if is_strict_int(expires_at_ms) else None),
            "oauth_has_refresh_token": has_refresh_token,
        }


async def clear_oauth_method(
    self: ExternalAccountsOAuthServiceProtocol,
    *,
    user_id: int,
    external_account_id: str,
) -> JSONDict:
    async with self.account_lock(
        user_id=user_id,
        external_account_id=external_account_id,
    ):
        current_account = await self.get_account(
            user_id,
            external_account_id,
            decrypt_secrets=False,
        )
        if current_account is None:
            raise ValidationError("External account not found.")
        require_oauth2_account(current_account)
        account = await self.update_account(
            user_id=user_id,
            external_account_id=external_account_id,
            updates=build_oauth_clear_updates(),
        )
        if account is None:
            raise ValidationError("External account not found.")
        return {"ok": True, "external_account_id": external_account_id, "oauth_status": "none"}


async def complete_oauth_callback_method(
    self: ExternalAccountsOAuthServiceProtocol,
    *,
    code: str,
    state_token: str,
    user_id: int,
) -> JSONDict:
    flow_state = decode_wrapped_oauth_flow_state(
        self.database_external_accounts.fernet,
        token=state_token,
        expected_token_type=OAUTH_STATE_TOKEN_TYPE_EXTERNAL_ACCOUNT,
        ttl_ms=self.oauth_state_token_ttl_ms,
        now_ms=epoch_ms(),
    )
    if flow_state.user_id != int(user_id):
        raise OAuthError(OAuthErrorCode.INVALID_STATE, "OAuth state user mismatch.")
    async with self.account_lock(
        user_id=user_id,
        external_account_id=flow_state.server_id,
    ):
        account = await self.get_account(
            user_id,
            flow_state.server_id,
            decrypt_secrets=True,
        )
        if account is None:
            raise ValidationError("External account not found.")
        require_oauth2_account(account)
        oauth_http = OAuthHTTPClientAdapter(self.http_client)

        validate_url = create_oauth_runtime_url_validator(self.runtime_flags)

        now_ms = epoch_ms
        tokens = await exchange_authorization_code_for_tokens(
            oauth_http,
            auth_server=build_account_auth_server(account),
            client=build_account_client_credentials(account),
            code=code,
            redirect_uri=flow_state.redirect_uri,
            code_verifier=flow_state.code_verifier,
            resource=flow_state.resource,
            validate_url=validate_url,
            now_ms=now_ms,
        )
        parsed_scopes = parse_scope_text(tokens.scope)
        granted_scopes = parsed_scopes or flow_state.scopes
        oauth_status = resolve_account_oauth_grant_status(
            account,
            granted_scopes=granted_scopes,
        )
        updated_account = await self.update_account(
            user_id=user_id,
            external_account_id=flow_state.server_id,
            updates=build_oauth_token_updates(
                oauth_status=oauth_status,
                tokens=tokens,
                retained_refresh_token=None,
            ),
        )
        if updated_account is None:
            raise ValidationError("External account not found.")
        return {
            "ok": True,
            "external_account_id": flow_state.server_id,
            "oauth_status": oauth_status,
        }
