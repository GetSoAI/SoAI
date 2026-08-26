"""SoAI - Shared account envelope formatting [backend/features/external_accounts/account_envelope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.external_accounts.state import resolve_effective_oauth_status
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, JSONValue
from core.validation.record_fields import (
    require_non_empty_str,
    require_optional_int,
    require_optional_str,
    require_str_list,
)
from features.external_accounts.external_account_fields import (
    require_external_account_auth_type,
)

__all__ = (
    "build_account_envelope",
    "resolve_external_account_oauth_status",
)


def build_account_envelope(
    *,
    account_id: str,
    account_type: str,
    default_label: str,
    external_account: JSONDict,
    supported_actions: list[str],
    capabilities: JSONDict,
    transport: JSONDict,
    raw_sync_at_ms: JSONValue,
    raw_sync_error: JSONValue,
) -> JSONDict:
    normalized_account_id = require_non_empty_str(
        account_id,
        label="account_id",
        build_error=StateError,
        invalid_message="account_id is invalid.",
    )
    auth_type = require_external_account_auth_type(
        external_account,
        build_error=StateError,
    )
    username = require_optional_str(
        external_account.get("username"),
        label="string value",
        build_error=StateError,
    )
    label = _resolve_label(default_label, external_account)
    oauth_expires_at_ms = require_optional_int(
        external_account.get("oauth_expires_at_ms"),
        label="timestamp value",
        build_error=StateError,
        minimum=0,
    )
    has_refresh_token = external_account.get("oauth_has_refresh_token") is True
    oauth_status = resolve_external_account_oauth_status(external_account)
    return {
        "account_id": normalized_account_id,
        "account_type": account_type,
        "label": label,
        "username": username,
        "auth": {
            "type": auth_type,
            "has_password": external_account.get("has_password") is True,
            "oauth": {
                "status": oauth_status,
                "expires_at_ms": oauth_expires_at_ms,
                "has_refresh_token": has_refresh_token,
                "client_id": require_optional_str(
                    external_account.get("oauth_client_id"),
                    label="string value",
                    build_error=StateError,
                ),
                "resource_metadata_url": require_optional_str(
                    external_account.get("oauth_resource_metadata_url"),
                    label="string value",
                    build_error=StateError,
                ),
                "auth_server_issuer": require_optional_str(
                    external_account.get("oauth_auth_server_issuer"),
                    label="string value",
                    build_error=StateError,
                ),
                "authorization_endpoint": require_optional_str(
                    external_account.get("oauth_authorization_endpoint"),
                    label="string value",
                    build_error=StateError,
                ),
                "token_endpoint": require_optional_str(
                    external_account.get("oauth_token_endpoint"),
                    label="string value",
                    build_error=StateError,
                ),
                "registration_endpoint": require_optional_str(
                    external_account.get("oauth_registration_endpoint"),
                    label="string value",
                    build_error=StateError,
                ),
                "token_endpoint_auth_method": require_optional_str(
                    external_account.get("oauth_token_endpoint_auth_method"),
                    label="string value",
                    build_error=StateError,
                ),
                "scopes": _read_optional_string_list(external_account.get("oauth_scopes")),
                "required_scopes": _read_optional_string_list(
                    external_account.get("oauth_required_scopes"),
                ),
            },
        },
        "sync": {
            "last_sync_at_ms": require_optional_int(
                raw_sync_at_ms,
                label="timestamp value",
                build_error=StateError,
                minimum=0,
            ),
            "last_sync_error": require_optional_str(
                raw_sync_error,
                label="string value",
                build_error=StateError,
            ),
        },
        "supported_actions": list(supported_actions),
        "capabilities": dict(capabilities),
        "transport": dict(transport),
    }


def resolve_external_account_oauth_status(external_account: JSONDict) -> str:
    has_refresh_token = external_account.get("oauth_has_refresh_token") is True
    return resolve_effective_oauth_status(
        oauth_status=external_account.get("oauth_status"),
        oauth_expires_at_ms=external_account.get("oauth_expires_at_ms"),
        has_refresh_token=has_refresh_token,
        now_ms=epoch_ms(),
    )


def _resolve_label(default_label: str, external_account: JSONDict) -> str:
    label_value = require_optional_str(
        external_account.get("label"),
        label="string value",
        build_error=StateError,
    )
    if label_value is not None:
        return label_value
    normalized_default = default_label.strip()
    return normalized_default


def _read_optional_string_list(value: JSONValue | None) -> list[str]:
    if value is None:
        return []
    return require_str_list(
        value,
        label="string list value",
        build_error=StateError,
        allow_empty=True,
    )
