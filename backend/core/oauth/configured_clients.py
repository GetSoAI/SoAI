"""SoAI - Configured OAuth metadata reconstruction helpers [backend/core/oauth/configured_clients.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.oauth.types import OAuthAuthorizationServerMetadata, OAuthClientCredentials

__all__ = (
    "build_configured_auth_server",
    "build_configured_client_credentials",
    "require_configured_oauth_text",
)


def require_configured_oauth_text(value: str | None, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Missing {label}.")
    return value.strip()


def build_configured_auth_server(
    *,
    issuer: str | None,
    authorization_endpoint: str | None,
    token_endpoint: str | None,
    registration_endpoint: str | None,
) -> OAuthAuthorizationServerMetadata:
    return OAuthAuthorizationServerMetadata(
        issuer=require_configured_oauth_text(issuer, "oauth_auth_server_issuer"),
        authorization_endpoint=require_configured_oauth_text(
            authorization_endpoint,
            "oauth_authorization_endpoint",
        ),
        token_endpoint=require_configured_oauth_text(token_endpoint, "oauth_token_endpoint"),
        registration_endpoint=(
            registration_endpoint.strip()
            if isinstance(registration_endpoint, str) and registration_endpoint.strip()
            else None
        ),
        token_endpoint_auth_methods_supported=None,
        code_challenge_methods_supported=("S256",),
        client_id_metadata_document_supported=False,
        raw={},
    )


def build_configured_client_credentials(
    *,
    client_id: str | None,
    client_secret: str | None,
    token_endpoint_auth_method: str | None,
) -> OAuthClientCredentials:
    return OAuthClientCredentials(
        client_id=require_configured_oauth_text(client_id, "oauth_client_id"),
        client_secret=(
            client_secret.strip()
            if isinstance(client_secret, str) and client_secret.strip()
            else None
        ),
        token_endpoint_auth_method=(
            token_endpoint_auth_method.strip()
            if isinstance(token_endpoint_auth_method, str) and token_endpoint_auth_method.strip()
            else "none"
        ),
    )
