"""SoAI - External account repository row builders [backend/database/repositories/users/external_accounts/row_builders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.external_accounts.storage import apply_external_account_write_canonicalization
from core.external_accounts.validation import validate_supported_external_account_fields
from core.security.secret_crypto import encrypt_optional_secret
from core.timing.epoch import epoch_ms
from core.users.account_identifiers import (
    EXTERNAL_ACCOUNT_ID_PREFIX,
    build_random_prefixed_identifier,
)
from core.validation.strings import coerce_optional_trimmed_str
from database.core.sqlite_values import SQLiteRowDict, SQLiteValue
from database.repositories.users.external_accounts.validation import (
    optional_epoch_ms,
    optional_oauth_status,
    optional_secret,
    optional_str_list_json,
    require_auth_type,
    require_text,
)

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from core.types.json import JSONDict

__all__ = (
    "build_external_account_insert_row",
    "build_external_account_update_row",
)


def build_external_account_insert_row(
    *,
    fernet: tuple[Fernet, ...],
    user_id: int,
    payload: JSONDict,
) -> SQLiteRowDict:
    validate_supported_external_account_fields(payload)
    now_ms = epoch_ms()
    auth_type = require_auth_type(payload.get("auth_type"))
    row: SQLiteRowDict = {
        "id": build_random_prefixed_identifier(EXTERNAL_ACCOUNT_ID_PREFIX),
        "user_id": user_id,
        "label": require_text(payload.get("label"), "label"),
        "username": require_text(payload.get("username"), "username"),
        "auth_type": auth_type,
        "password_encrypted": encrypt_optional_secret(
            fernet,
            optional_secret(payload.get("password")),
            label="external account password",
        ),
        "oauth_status": optional_oauth_status(payload.get("oauth_status")),
        "oauth_client_id": coerce_optional_trimmed_str(payload.get("oauth_client_id")),
        "oauth_client_secret_encrypted": encrypt_optional_secret(
            fernet,
            optional_secret(payload.get("oauth_client_secret")),
            label="external account oauth_client_secret",
        ),
        "oauth_access_token_encrypted": encrypt_optional_secret(
            fernet,
            optional_secret(payload.get("oauth_access_token")),
            label="external account oauth_access_token",
        ),
        "oauth_refresh_token_encrypted": encrypt_optional_secret(
            fernet,
            optional_secret(payload.get("oauth_refresh_token")),
            label="external account oauth_refresh_token",
        ),
        "oauth_expires_at_ms": optional_epoch_ms(payload.get("oauth_expires_at_ms")),
        "oauth_resource_metadata_url": coerce_optional_trimmed_str(
            payload.get("oauth_resource_metadata_url"),
        ),
        "oauth_auth_server_issuer": coerce_optional_trimmed_str(
            payload.get("oauth_auth_server_issuer"),
        ),
        "oauth_authorization_endpoint": coerce_optional_trimmed_str(
            payload.get("oauth_authorization_endpoint"),
        ),
        "oauth_token_endpoint": coerce_optional_trimmed_str(payload.get("oauth_token_endpoint")),
        "oauth_registration_endpoint": coerce_optional_trimmed_str(
            payload.get("oauth_registration_endpoint"),
        ),
        "oauth_token_endpoint_auth_method": coerce_optional_trimmed_str(
            payload.get("oauth_token_endpoint_auth_method"),
        ),
        "oauth_scopes": optional_str_list_json(payload.get("oauth_scopes")),
        "oauth_required_scopes": optional_str_list_json(payload.get("oauth_required_scopes")),
        "created_at_ms": now_ms,
        "last_modified_at_ms": now_ms,
    }
    apply_external_account_write_canonicalization(row, auth_type=auth_type)
    return row


def build_external_account_update_row(
    *,
    fernet: tuple[Fernet, ...],
    updates: JSONDict,
) -> dict[str, SQLiteValue]:
    if not updates:
        raise ValidationError("updates must not be empty.")
    validate_supported_external_account_fields(updates)
    mapped: dict[str, SQLiteValue] = {"last_modified_at_ms": epoch_ms()}
    auth_type: str | None = None
    for key, value in updates.items():
        if key == "label":
            mapped["label"] = require_text(value, "label")
        elif key == "username":
            mapped["username"] = require_text(value, "username")
        elif key == "auth_type":
            auth_type = require_auth_type(value)
            mapped["auth_type"] = auth_type
        elif key == "password":
            mapped["password_encrypted"] = encrypt_optional_secret(
                fernet,
                optional_secret(value),
                label="external account password",
            )
        elif key == "oauth_status":
            mapped["oauth_status"] = optional_oauth_status(value)
        elif key == "oauth_client_id":
            mapped["oauth_client_id"] = coerce_optional_trimmed_str(value)
        elif key == "oauth_client_secret":
            mapped["oauth_client_secret_encrypted"] = encrypt_optional_secret(
                fernet,
                optional_secret(value),
                label="external account oauth_client_secret",
            )
        elif key == "oauth_access_token":
            mapped["oauth_access_token_encrypted"] = encrypt_optional_secret(
                fernet,
                optional_secret(value),
                label="external account oauth_access_token",
            )
        elif key == "oauth_refresh_token":
            mapped["oauth_refresh_token_encrypted"] = encrypt_optional_secret(
                fernet,
                optional_secret(value),
                label="external account oauth_refresh_token",
            )
        elif key == "oauth_expires_at_ms":
            mapped["oauth_expires_at_ms"] = optional_epoch_ms(value)
        elif key in {
            "oauth_resource_metadata_url",
            "oauth_auth_server_issuer",
            "oauth_authorization_endpoint",
            "oauth_token_endpoint",
            "oauth_registration_endpoint",
            "oauth_token_endpoint_auth_method",
        }:
            mapped[key] = coerce_optional_trimmed_str(value)
        elif key == "oauth_scopes":
            mapped["oauth_scopes"] = optional_str_list_json(value)
        elif key == "oauth_required_scopes":
            mapped["oauth_required_scopes"] = optional_str_list_json(value)
    if auth_type is not None:
        apply_external_account_write_canonicalization(mapped, auth_type=auth_type)
    return mapped
