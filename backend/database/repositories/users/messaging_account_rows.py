"""SoAI - Safe Messaging account row materialization [backend/database/repositories/users/messaging_account_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.messaging.account_validation import (
    require_messaging_account_label,
    require_messaging_account_lifecycle_state,
    require_messaging_account_locale,
    require_messaging_platform,
    require_messaging_principal_id,
    validate_messaging_model_settings,
)
from core.types.json import is_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from database.core.row_fields import (
    require_row_bool,
    require_row_epoch_ms,
    require_row_json_list,
    require_row_json_object,
    require_row_non_empty_str,
    require_row_non_negative_int,
    require_row_positive_int,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("format_messaging_account_row",)


def format_messaging_account_row(row: SQLiteRowDict | None) -> JSONDict | None:
    if row is None:
        return None
    try:
        platform = require_messaging_platform(
            require_row_non_empty_str(
                row.get("platform"),
                label="Messaging account platform",
                build_error=StateError,
            ),
        )
        lifecycle_state = require_messaging_account_lifecycle_state(
            require_row_non_empty_str(
                row.get("lifecycle_state"),
                label="Messaging account lifecycle state",
                build_error=StateError,
            ),
        )
        locale = require_messaging_account_locale(
            require_row_non_empty_str(
                row.get("locale"),
                label="Messaging account locale",
                build_error=StateError,
            ),
        )
        model_settings = validate_messaging_model_settings(
            require_row_json_object(
                row.get("model_settings_json"),
                label="Messaging account model settings",
                build_error=StateError,
            ),
        )
    except ValidationError as exception:
        raise StateError("Stored Messaging account data is invalid.") from exception
    credential_ciphertext = require_row_non_empty_str(
        row.get("credential_ciphertext"),
        label="Messaging account encrypted credentials",
        build_error=StateError,
    )
    return {
        "account_id": require_row_non_empty_str(
            row.get("account_id"),
            label="Messaging account id",
            build_error=StateError,
        ),
        "user_id": require_row_positive_int(
            row.get("user_id"),
            label="Messaging account user id",
            build_error=StateError,
        ),
        "platform": platform,
        "label": _require_stored_label(
            require_row_non_empty_str(
                row.get("label"),
                label="Messaging account label",
                build_error=StateError,
            ),
        ),
        "principal_id": _require_stored_principal(
            require_row_non_empty_str(
                row.get("principal_id"),
                label="Messaging account principal id",
                build_error=StateError,
            ),
            label="Messaging account principal id",
        ),
        "principal_label": _optional_str(row.get("principal_label")),
        "parent_principal_id": _optional_str(row.get("parent_principal_id")),
        "application_principal_id": _optional_str(
            row.get("application_principal_id"),
        ),
        "credential_configured": bool(credential_ciphertext),
        "model_settings": model_settings,
        "locale": locale,
        "lifecycle_state": lifecycle_state,
        "revision": require_row_positive_int(
            row.get("revision"),
            label="Messaging account revision",
            build_error=StateError,
        ),
        "lifecycle_generation": require_row_non_negative_int(
            row.get("lifecycle_generation"),
            label="Messaging account lifecycle generation",
            build_error=StateError,
        ),
        "plaintext_secret_replies_enabled": require_row_bool(
            row.get("plaintext_secret_replies_enabled"),
            label="Messaging account plaintext secret replies",
            build_error=StateError,
        ),
        "accept_messages_from_anyone": require_row_bool(
            row.get("accept_messages_from_anyone"),
            label="Messaging account unrestricted sender access",
            build_error=StateError,
        ),
        "installed_callback_fingerprint": _optional_str(
            row.get("installed_callback_fingerprint"),
        ),
        "callback_ownership_state": require_row_non_empty_str(
            row.get("callback_ownership_state"),
            label="Messaging account callback ownership",
            build_error=StateError,
        ),
        "health_code": _optional_str(row.get("health_code")),
        "health_checked_at_ms": _optional_epoch(row.get("health_checked_at_ms")),
        "created_at_ms": require_row_epoch_ms(
            row.get("created_at_ms"),
            label="Messaging account created time",
            build_error=StateError,
        ),
        "updated_at_ms": require_row_epoch_ms(
            row.get("updated_at_ms"),
            label="Messaging account updated time",
            build_error=StateError,
        ),
        "authorized_senders": _format_authorized_senders(row),
    }


def _format_authorized_senders(row: SQLiteRowDict) -> list[JSONDict]:
    values = require_row_json_list(
        row.get("authorized_senders_json"),
        label="Messaging authorized senders",
        build_error=StateError,
    )
    senders: list[JSONDict] = []
    for value in values:
        if not is_json_dict(value):
            raise StateError("Messaging authorized sender row is invalid.")
        senders.append(
            {
                "sender_id": _require_stored_principal(
                    require_row_non_empty_str(
                        value.get("sender_id"),
                        label="Messaging authorized sender id",
                        build_error=StateError,
                    ),
                    label="Messaging authorized sender id",
                ),
                "display_label": _optional_str(value.get("display_label")),
            },
        )
    return senders


def _optional_str(value: JSONValue | bytes) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StateError("Stored Messaging account text is invalid.")
    return coerce_optional_trimmed_str(value)


def _optional_epoch(value: str | int | float | bytes | None) -> int | None:
    if value is None:
        return None
    return require_row_epoch_ms(
        value,
        label="Messaging account health checked time",
        build_error=StateError,
    )


def _require_stored_label(value: str) -> str:
    try:
        return require_messaging_account_label(value)
    except ValidationError as exception:
        raise StateError("Stored Messaging account label is invalid.") from exception


def _require_stored_principal(value: str, *, label: str) -> str:
    try:
        return require_messaging_principal_id(value, label=label)
    except ValidationError as exception:
        raise StateError(f"Stored {label.lower()} is invalid.") from exception
