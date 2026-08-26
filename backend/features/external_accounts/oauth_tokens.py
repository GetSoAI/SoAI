"""SoAI - External account OAuth token helpers [backend/features/external_accounts/oauth_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.external_accounts.oauth_config import (
    build_account_auth_server,
    build_account_client_credentials,
    resolve_account_oauth_grant_status,
    resolve_account_requested_scopes,
    resolve_account_resource,
)
from core.external_accounts.oauth_updates import build_oauth_token_updates
from core.external_accounts.state import (
    parse_scope_text,
    raise_for_oauth_status,
)
from core.oauth.flows import oauth_token_expires_within_skew, refresh_access_token
from core.oauth.http_client_adapter import OAuthHTTPClientAdapter
from core.oauth.types import OAuthError, OAuthErrorCode
from core.oauth.url_policy import create_oauth_runtime_url_validator
from core.serialization.base64_values import encode_base64_ascii
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.strings import coerce_optional_trimmed_str
from features.external_accounts.account_envelope import (
    resolve_external_account_oauth_status,
)
from features.external_accounts.internal_protocols import (
    ExternalAccountsOAuthServiceProtocol,
)
from features.external_accounts.oauth_account_loading import (
    locked_oauth2_external_account,
)

__all__ = (
    "build_xoauth2_sasl_method",
    "get_access_token_method",
)


async def get_access_token_method(
    self: ExternalAccountsOAuthServiceProtocol,
    *,
    user_id: int,
    external_account_id: str,
) -> JSONDict:
    async with locked_oauth2_external_account(
        self,
        user_id=user_id,
        external_account_id=external_account_id,
    ) as account:
        oauth_status = resolve_external_account_oauth_status(account)
        if oauth_status != "ready":
            raise_for_oauth_status(oauth_status)
        access_token = coerce_optional_trimmed_str(account.get("oauth_access_token"))
        expires_at_ms = account.get("oauth_expires_at_ms")
        if (
            access_token is not None
            and isinstance(expires_at_ms, int)
            and not isinstance(expires_at_ms, bool)
            and not oauth_token_expires_within_skew(
                expires_at_ms,
                now_ms=epoch_ms(),
                skew_ms=self.oauth_refresh_skew_ms,
            )
        ):
            return {
                "access_token": access_token,
                "expires_at_ms": expires_at_ms,
                "oauth_status": oauth_status,
            }
        refresh_token_value = coerce_optional_trimmed_str(account.get("oauth_refresh_token"))
        if refresh_token_value is None:
            raise OAuthError(
                OAuthErrorCode.AUTH_REQUIRED,
                "OAuth refresh token is not available for this account.",
            )
        oauth_http = OAuthHTTPClientAdapter(self.http_client)

        validate_url = create_oauth_runtime_url_validator(self.runtime_flags)

        tokens = await refresh_access_token(
            oauth_http,
            auth_server=build_account_auth_server(account),
            client=build_account_client_credentials(account),
            refresh_token=refresh_token_value,
            resource=resolve_account_resource(account, None),
            validate_url=validate_url,
            now_ms=epoch_ms,
        )
        oauth_status = resolve_account_oauth_grant_status(
            account,
            granted_scopes=parse_scope_text(tokens.scope)
            or resolve_account_requested_scopes(account),
        )
        updated_account = await self.update_account(
            user_id=user_id,
            external_account_id=external_account_id,
            updates=build_oauth_token_updates(
                oauth_status=oauth_status,
                tokens=tokens,
                retained_refresh_token=refresh_token_value,
            ),
        )
        if updated_account is None:
            raise ValidationError("External account not found.")
        if oauth_status != "ready":
            raise_for_oauth_status(oauth_status)
        return {
            "access_token": tokens.access_token,
            "expires_at_ms": tokens.expires_at_ms,
            "oauth_status": oauth_status,
        }


def build_xoauth2_sasl_method(
    self: ExternalAccountsOAuthServiceProtocol,
    *,
    user_email: str,
    access_token: str,
) -> str:
    _ = self
    normalized_user = str(user_email or "").strip()
    normalized_token = str(access_token or "").strip()
    if not normalized_user:
        raise ValidationError("user_email is required.")
    if not normalized_token:
        raise ValidationError("access_token is required.")
    payload = f"user={normalized_user}\x01auth=Bearer {normalized_token}\x01\x01"
    return encode_base64_ascii(payload.encode("utf-8"))
