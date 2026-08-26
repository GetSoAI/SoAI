"""SoAI - External account OAuth configuration helpers [backend/core/external_accounts/oauth_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.external_accounts.state import (
    read_scope_field,
    require_oauth2_account,
    resolve_oauth_grant_status,
)
from core.oauth.configured_clients import (
    build_configured_auth_server,
    build_configured_client_credentials,
)
from core.oauth.types import (
    OAuthAuthorizationServerMetadata,
    OAuthClientCredentials,
    OAuthProtectedResourceMetadata,
)
from core.types.json import JSONDict
from core.validation.record_fields import require_non_empty_str, require_optional_str

__all__ = (
    "build_account_auth_server",
    "build_account_client_credentials",
    "read_optional_account_text",
    "resolve_account_issuer",
    "resolve_account_oauth_grant_status",
    "resolve_account_requested_scopes",
    "resolve_account_required_scopes",
    "resolve_account_resource",
    "resolve_account_scopes",
)


def build_account_auth_server(account: JSONDict) -> OAuthAuthorizationServerMetadata:
    require_oauth2_account(account)
    return build_configured_auth_server(
        issuer=require_non_empty_str(
            account.get("oauth_auth_server_issuer"),
            label="oauth_auth_server_issuer",
            build_error=ValidationError,
            invalid_message="oauth_auth_server_issuer is required.",
        ),
        authorization_endpoint=require_non_empty_str(
            account.get("oauth_authorization_endpoint"),
            label="oauth_authorization_endpoint",
            build_error=ValidationError,
            invalid_message="oauth_authorization_endpoint is required.",
        ),
        token_endpoint=require_non_empty_str(
            account.get("oauth_token_endpoint"),
            label="oauth_token_endpoint",
            build_error=ValidationError,
            invalid_message="oauth_token_endpoint is required.",
        ),
        registration_endpoint=read_optional_account_text(
            account,
            "oauth_registration_endpoint",
        ),
    )


def build_account_client_credentials(account: JSONDict) -> OAuthClientCredentials:
    require_oauth2_account(account)
    return build_configured_client_credentials(
        client_id=require_non_empty_str(
            account.get("oauth_client_id"),
            label="oauth_client_id",
            build_error=ValidationError,
            invalid_message="oauth_client_id is required.",
        ),
        client_secret=read_optional_account_text(account, "oauth_client_secret"),
        token_endpoint_auth_method=read_optional_account_text(
            account,
            "oauth_token_endpoint_auth_method",
        ),
    )


def resolve_account_resource(account: JSONDict, resource: str | None) -> str:
    explicit_resource = require_optional_str(
        resource,
        label="resource",
        build_error=ValidationError,
        invalid_message="resource must be a string or null.",
    )
    if explicit_resource is not None:
        return explicit_resource
    stored_resource = read_optional_account_text(account, "oauth_resource_metadata_url")
    if stored_resource is None:
        raise ValidationError("OAuth resource URL is required.")
    return stored_resource


def resolve_account_issuer(
    account: JSONDict,
    protected_resource: OAuthProtectedResourceMetadata,
) -> str:
    configured_issuer = read_optional_account_text(account, "oauth_auth_server_issuer")
    if configured_issuer is not None:
        return configured_issuer
    if not protected_resource.authorization_servers:
        raise ValidationError("OAuth authorization server metadata is missing.")
    issuer = protected_resource.authorization_servers[0]
    if not issuer.strip():
        raise ValidationError("OAuth authorization server issuer is invalid.")
    return issuer.strip()


def resolve_account_required_scopes(account: JSONDict) -> tuple[str, ...]:
    return read_scope_field(account.get("oauth_required_scopes"), label="oauth_required_scopes")


def resolve_account_requested_scopes(account: JSONDict) -> tuple[str, ...]:
    configured_scopes = read_scope_field(account.get("oauth_scopes"), label="oauth_scopes")
    if configured_scopes:
        return configured_scopes
    return resolve_account_required_scopes(account)


def resolve_account_scopes(
    account: JSONDict,
    protected_resource: OAuthProtectedResourceMetadata,
) -> tuple[str, ...]:
    configured_scopes = resolve_account_requested_scopes(account)
    if configured_scopes:
        return configured_scopes
    supported_scopes = protected_resource.scopes_supported
    if supported_scopes is None:
        return ()
    normalized: list[str] = []
    for entry in supported_scopes:
        scope = entry.strip()
        if scope and scope not in normalized:
            normalized.append(scope)
    return tuple(normalized)


def resolve_account_oauth_grant_status(
    account: JSONDict,
    *,
    granted_scopes: tuple[str, ...],
) -> str:
    return resolve_oauth_grant_status(
        required_scopes=resolve_account_required_scopes(account),
        granted_scopes=granted_scopes,
    )


def read_optional_account_text(account: JSONDict, field_name: str) -> str | None:
    return require_optional_str(
        account.get(field_name),
        label=field_name,
        build_error=ValidationError,
        invalid_message=f"{field_name} must be a string or null.",
    )
