"""SoAI - External account row normalization [backend/database/repositories/users/external_accounts/record_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.errors.exceptions import StateError, ValidationError
from core.external_accounts.state import require_auth_type
from core.external_accounts.storage import apply_external_account_read_canonicalization
from core.security.secret_crypto import decrypt_optional_secret
from core.serialization.json_parsing import parse_json_str_list
from core.types.json import JSONDict, JSONValue
from core.validation.strings import coerce_optional_trimmed_str
from database.repositories.row_formatting import format_row

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteValue

__all__ = ("normalize_external_account_row",)


def normalize_external_account_row(
    row: Mapping[str, SQLiteValue] | None,
    *,
    fernet: Sequence[Fernet],
    decrypt_secrets: bool,
) -> JSONDict | None:
    formatted = format_row(row)
    if formatted is None:
        return None
    password_encrypted = _coerce_optional_str(
        formatted.get("password_encrypted"),
        label="password_encrypted",
    )
    client_secret_encrypted = _coerce_optional_str(
        formatted.get("oauth_client_secret_encrypted"),
        label="oauth_client_secret_encrypted",
    )
    access_token_encrypted = _coerce_optional_str(
        formatted.get("oauth_access_token_encrypted"),
        label="oauth_access_token_encrypted",
    )
    refresh_token_encrypted = _coerce_optional_str(
        formatted.get("oauth_refresh_token_encrypted"),
        label="oauth_refresh_token_encrypted",
    )
    formatted["oauth_scopes"] = _parse_optional_str_list(
        formatted.get("oauth_scopes"),
        label="oauth_scopes",
    )
    formatted["oauth_required_scopes"] = _parse_optional_str_list(
        formatted.get("oauth_required_scopes"),
        label="oauth_required_scopes",
    )
    formatted["has_password"] = password_encrypted is not None
    formatted["oauth_has_refresh_token"] = refresh_token_encrypted is not None
    if decrypt_secrets:
        formatted["password"] = decrypt_optional_secret(
            fernet,
            password_encrypted,
            label="external account password",
        )
        formatted["oauth_client_secret"] = decrypt_optional_secret(
            fernet,
            client_secret_encrypted,
            label="external account oauth_client_secret",
        )
        formatted["oauth_access_token"] = decrypt_optional_secret(
            fernet,
            access_token_encrypted,
            label="external account oauth_access_token",
        )
        formatted["oauth_refresh_token"] = decrypt_optional_secret(
            fernet,
            refresh_token_encrypted,
            label="external account oauth_refresh_token",
        )
    apply_external_account_read_canonicalization(
        formatted,
        auth_type=require_auth_type(formatted.get("auth_type")),
    )
    formatted.pop("password_encrypted", None)
    formatted.pop("oauth_client_secret_encrypted", None)
    formatted.pop("oauth_access_token_encrypted", None)
    formatted.pop("oauth_refresh_token_encrypted", None)
    return formatted


def _coerce_optional_str(value: JSONValue, *, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StateError(f"{label} is invalid.")
    return coerce_optional_trimmed_str(value)


def _parse_optional_str_list(value: JSONValue, *, label: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"{label} is invalid.")
    try:
        parsed = parse_json_str_list(value, field=label, strip_items=True)
    except ValidationError as exception:
        raise StateError(f"{label} is invalid.") from exception
    if not parsed:
        raise StateError(f"{label} is invalid.")
    for item in parsed:
        if not item:
            raise StateError(f"{label} is invalid.")
    return parsed
