"""SoAI - External account storage canonicalization helpers [backend/core/external_accounts/storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import MutableMapping

from core.external_accounts.state import (
    AUTH_TYPE_FORM_CREDENTIAL,
    AUTH_TYPE_OAUTH2,
    OAUTH_STATUS_NONE,
)
from core.types.json import JSONDict

__all__ = (
    "apply_external_account_read_canonicalization",
    "apply_external_account_write_canonicalization",
)


def apply_external_account_write_canonicalization(
    row: MutableMapping[str, int | float | str | bytes | None],
    *,
    auth_type: str,
) -> None:
    if auth_type == AUTH_TYPE_FORM_CREDENTIAL:
        row["oauth_status"] = OAUTH_STATUS_NONE
        row["oauth_client_id"] = None
        row["oauth_client_secret_encrypted"] = None
        row["oauth_access_token_encrypted"] = None
        row["oauth_refresh_token_encrypted"] = None
        row["oauth_expires_at_ms"] = None
        row["oauth_resource_metadata_url"] = None
        row["oauth_auth_server_issuer"] = None
        row["oauth_authorization_endpoint"] = None
        row["oauth_token_endpoint"] = None
        row["oauth_registration_endpoint"] = None
        row["oauth_token_endpoint_auth_method"] = None
        row["oauth_scopes"] = None
        row["oauth_required_scopes"] = None
        return
    if auth_type == AUTH_TYPE_OAUTH2:
        row["password_encrypted"] = None


def apply_external_account_read_canonicalization(
    formatted: JSONDict,
    *,
    auth_type: str,
) -> None:
    if auth_type == AUTH_TYPE_FORM_CREDENTIAL:
        formatted["oauth_status"] = OAUTH_STATUS_NONE
        formatted["oauth_client_id"] = None
        formatted["oauth_client_secret"] = None
        formatted["oauth_access_token"] = None
        formatted["oauth_refresh_token"] = None
        formatted["oauth_expires_at_ms"] = None
        formatted["oauth_resource_metadata_url"] = None
        formatted["oauth_auth_server_issuer"] = None
        formatted["oauth_authorization_endpoint"] = None
        formatted["oauth_token_endpoint"] = None
        formatted["oauth_registration_endpoint"] = None
        formatted["oauth_token_endpoint_auth_method"] = None
        formatted["oauth_scopes"] = None
        formatted["oauth_required_scopes"] = None
        formatted["oauth_has_refresh_token"] = False
        return
    if auth_type == AUTH_TYPE_OAUTH2:
        formatted["password"] = None
        formatted["has_password"] = False
