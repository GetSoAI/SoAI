"""SoAI - External account repository validation [backend/database/repositories/users/external_accounts/validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.external_accounts.state import (
    coerce_oauth_status,
    require_auth_type,
)
from core.security.secret_crypto import coerce_optional_secret_plaintext
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str
from database.core.json_codec import serialize_required_json_list_field
from database.repositories.users.account_validation import (
    require_epoch_ms,
    require_text,
    require_user_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "optional_epoch_ms",
    "optional_oauth_status",
    "optional_secret",
    "optional_str_list_json",
    "require_auth_type",
    "require_text",
    "require_user_id",
)


def optional_secret(value: JSONValue) -> str | None:
    return coerce_optional_secret_plaintext(value, label="secret value")


def optional_oauth_status(value: JSONValue) -> str:
    if value is None:
        return "none"
    return coerce_oauth_status(value)


def optional_epoch_ms(value: JSONValue) -> int | None:
    if value is None:
        return None
    if not is_strict_int(value):
        raise ValidationError("oauth_expires_at_ms must be an integer or null.")
    return require_epoch_ms(value, "oauth_expires_at_ms")


def optional_str_list_json(value: JSONValue) -> str | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValidationError("OAuth scopes must be a list of strings or null.")
    normalized_items: list[str] = []
    for item in value:
        normalized = coerce_optional_trimmed_str(item)
        if normalized is None:
            raise ValidationError("OAuth scopes must be a list of strings or null.")
        normalized_items.append(normalized)
    return (
        serialize_required_json_list_field(
            normalized_items,
            error_message="OAuth scopes must be a list of strings or null.",
        )
        if normalized_items
        else None
    )
