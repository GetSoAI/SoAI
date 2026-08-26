"""SoAI - Shared OAuth update payload builders [backend/core/external_accounts/oauth_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.external_accounts.state import (
    OAUTH_STATUS_AUTH_REQUIRED,
    OAUTH_STATUS_ERROR,
    OAUTH_STATUS_INSUFFICIENT_SCOPE,
    OAUTH_STATUS_NONE,
    coerce_oauth_status,
    parse_scope_text,
)
from core.oauth.types import (
    OAuthAuthorizationServerMetadata,
    OAuthChallenge,
    OAuthClientCredentials,
    OAuthTokens,
)
from core.oauth.www_authenticate import parse_www_authenticate_bearer_challenge
from core.types.json import JSONDict

__all__ = (
    "build_oauth_auth_error_updates",
    "build_oauth_clear_updates",
    "build_oauth_connection_updates",
    "build_oauth_disconnect_updates",
    "build_oauth_token_updates",
)


def build_oauth_connection_updates(
    *,
    client_credentials: OAuthClientCredentials,
    auth_server: OAuthAuthorizationServerMetadata,
    resource_metadata_url: str,
) -> JSONDict:
    return {
        "oauth_status": OAUTH_STATUS_AUTH_REQUIRED,
        "oauth_client_id": client_credentials.client_id,
        "oauth_client_secret": client_credentials.client_secret,
        "oauth_access_token": None,
        "oauth_refresh_token": None,
        "oauth_expires_at_ms": None,
        "oauth_resource_metadata_url": resource_metadata_url,
        "oauth_auth_server_issuer": auth_server.issuer,
        "oauth_authorization_endpoint": auth_server.authorization_endpoint,
        "oauth_token_endpoint": auth_server.token_endpoint,
        "oauth_registration_endpoint": auth_server.registration_endpoint,
        "oauth_token_endpoint_auth_method": client_credentials.token_endpoint_auth_method,
    }


def build_oauth_token_updates(
    *,
    oauth_status: str,
    tokens: OAuthTokens,
    retained_refresh_token: str | None,
) -> JSONDict:
    normalized_oauth_status = coerce_oauth_status(oauth_status)
    return {
        "oauth_status": normalized_oauth_status,
        "oauth_access_token": tokens.access_token,
        "oauth_refresh_token": tokens.refresh_token or retained_refresh_token,
        "oauth_expires_at_ms": tokens.expires_at_ms,
    }


def build_oauth_clear_updates() -> JSONDict:
    updates: JSONDict = {
        "oauth_status": OAUTH_STATUS_NONE,
        "oauth_access_token": None,
        "oauth_refresh_token": None,
        "oauth_expires_at_ms": None,
    }
    return updates


def build_oauth_disconnect_updates() -> JSONDict:
    updates = build_oauth_clear_updates()
    updates["oauth_client_id"] = None
    updates["oauth_client_secret"] = None
    updates["oauth_resource_metadata_url"] = None
    updates["oauth_auth_server_issuer"] = None
    updates["oauth_authorization_endpoint"] = None
    updates["oauth_token_endpoint"] = None
    updates["oauth_registration_endpoint"] = None
    updates["oauth_token_endpoint_auth_method"] = None
    updates["oauth_scopes"] = None
    updates["oauth_required_scopes"] = None
    return updates


def build_oauth_auth_error_updates(
    *,
    status_code: int,
    www_authenticate: str | None,
) -> tuple[JSONDict, str]:
    challenge = parse_www_authenticate_bearer_challenge(www_authenticate)
    updates: JSONDict = {}
    if challenge is not None and challenge.resource_metadata is not None:
        updates["oauth_resource_metadata_url"] = challenge.resource_metadata
    error_message: str
    if status_code == 401:
        updates["oauth_status"] = OAUTH_STATUS_AUTH_REQUIRED
        error_message = "Authorization required."
    elif status_code == 403 and challenge is not None and _is_insufficient_scope(challenge):
        updates["oauth_status"] = OAUTH_STATUS_INSUFFICIENT_SCOPE
        updates["oauth_required_scopes"] = list(_parse_scopes(challenge))
        error_message = "Insufficient OAuth scope."
    else:
        updates["oauth_status"] = OAUTH_STATUS_ERROR
        error_message = f"OAuth error (HTTP {status_code})."
    return (updates, error_message)


def _is_insufficient_scope(challenge: OAuthChallenge | None) -> bool:
    return challenge is not None and challenge.error == "insufficient_scope"


def _parse_scopes(challenge: OAuthChallenge) -> tuple[str, ...]:
    return parse_scope_text(challenge.scope)
