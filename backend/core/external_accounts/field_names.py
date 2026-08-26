"""SoAI - External account field name contracts [backend/core/external_accounts/field_names.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "EXTERNAL_ACCOUNT_FIELD_NAMES",
    "EXTERNAL_ACCOUNT_INSERT_COLUMN_NAMES",
    "EXTERNAL_ACCOUNT_OAUTH_CONFIGURATION_FIELD_NAMES",
    "EXTERNAL_ACCOUNT_OAUTH_FIELD_NAMES",
    "EXTERNAL_ACCOUNT_UPDATE_COLUMN_NAMES",
)

EXTERNAL_ACCOUNT_OAUTH_CONFIGURATION_FIELD_NAMES: tuple[str, ...] = (
    "oauth_status",
    "oauth_client_id",
    "oauth_client_secret",
    "oauth_resource_metadata_url",
    "oauth_auth_server_issuer",
    "oauth_authorization_endpoint",
    "oauth_token_endpoint",
    "oauth_registration_endpoint",
    "oauth_token_endpoint_auth_method",
    "oauth_scopes",
    "oauth_required_scopes",
)
EXTERNAL_ACCOUNT_OAUTH_FIELD_NAMES: tuple[str, ...] = (
    "oauth_status",
    "oauth_client_id",
    "oauth_client_secret",
    "oauth_access_token",
    "oauth_refresh_token",
    "oauth_expires_at_ms",
    "oauth_resource_metadata_url",
    "oauth_auth_server_issuer",
    "oauth_authorization_endpoint",
    "oauth_token_endpoint",
    "oauth_registration_endpoint",
    "oauth_token_endpoint_auth_method",
    "oauth_scopes",
    "oauth_required_scopes",
)
EXTERNAL_ACCOUNT_FIELD_NAMES: tuple[str, ...] = (
    "label",
    "username",
    "auth_type",
    "password",
    *EXTERNAL_ACCOUNT_OAUTH_FIELD_NAMES,
)
EXTERNAL_ACCOUNT_INSERT_COLUMN_NAMES: tuple[str, ...] = (
    "id",
    "user_id",
    "label",
    "username",
    "auth_type",
    "password_encrypted",
    "oauth_status",
    "oauth_client_id",
    "oauth_client_secret_encrypted",
    "oauth_access_token_encrypted",
    "oauth_refresh_token_encrypted",
    "oauth_expires_at_ms",
    "oauth_resource_metadata_url",
    "oauth_auth_server_issuer",
    "oauth_authorization_endpoint",
    "oauth_token_endpoint",
    "oauth_registration_endpoint",
    "oauth_token_endpoint_auth_method",
    "oauth_scopes",
    "oauth_required_scopes",
    "created_at_ms",
    "last_modified_at_ms",
)
EXTERNAL_ACCOUNT_UPDATE_COLUMN_NAMES: tuple[str, ...] = (
    "label",
    "username",
    "auth_type",
    "password_encrypted",
    "oauth_status",
    "oauth_client_id",
    "oauth_client_secret_encrypted",
    "oauth_access_token_encrypted",
    "oauth_refresh_token_encrypted",
    "oauth_expires_at_ms",
    "oauth_resource_metadata_url",
    "oauth_auth_server_issuer",
    "oauth_authorization_endpoint",
    "oauth_token_endpoint",
    "oauth_registration_endpoint",
    "oauth_token_endpoint_auth_method",
    "oauth_scopes",
    "oauth_required_scopes",
    "last_modified_at_ms",
)
