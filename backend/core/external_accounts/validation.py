"""SoAI - External account payload validation helpers [backend/core/external_accounts/validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.external_accounts.field_names import (
    EXTERNAL_ACCOUNT_FIELD_NAMES,
    EXTERNAL_ACCOUNT_OAUTH_FIELD_NAMES,
)
from core.external_accounts.state import (
    AUTH_TYPE_FORM_CREDENTIAL,
    OAUTH_STATUS_NONE,
    require_auth_type,
)
from core.types.json import JSONDict, JSONValue, is_json_dict
from core.validation.json_object_fields import validate_allowed_json_object_fields
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "validate_external_account_create_payload",
    "validate_external_account_update_payload",
    "validate_supported_external_account_fields",
)


def validate_external_account_create_payload(payload: JSONDict) -> None:
    validate_supported_external_account_fields(payload)
    auth_type = require_auth_type(payload.get("auth_type"))
    _validate_auth_type_payload_shape(auth_type=auth_type, payload=payload)
    if (
        auth_type == AUTH_TYPE_FORM_CREDENTIAL
        and coerce_optional_trimmed_str(payload.get("password")) is None
    ):
        raise ValidationError("password is required for password external accounts.")


def validate_external_account_update_payload(
    *,
    current_account: JSONDict,
    updates: JSONDict,
) -> None:
    if not updates:
        raise ValidationError("updates must not be empty.")
    validate_supported_external_account_fields(updates)
    current_auth_type = require_auth_type(current_account.get("auth_type"))
    effective_auth_type = (
        require_auth_type(updates.get("auth_type")) if "auth_type" in updates else current_auth_type
    )
    _validate_auth_type_payload_shape(auth_type=effective_auth_type, payload=updates)
    if effective_auth_type != AUTH_TYPE_FORM_CREDENTIAL:
        return
    if "password" in updates:
        if coerce_optional_trimmed_str(updates.get("password")) is None:
            raise ValidationError("password is required for password external accounts.")
        return
    if (
        current_auth_type != AUTH_TYPE_FORM_CREDENTIAL
        or current_account.get("has_password") is not True
    ):
        raise ValidationError("password is required for password external accounts.")


def _validate_auth_type_payload_shape(*, auth_type: str, payload: JSONDict) -> None:
    if auth_type == AUTH_TYPE_FORM_CREDENTIAL:
        for field_name in EXTERNAL_ACCOUNT_OAUTH_FIELD_NAMES:
            if _has_oauth_field_content(field_name=field_name, value=payload.get(field_name)):
                raise ValidationError(
                    f"{field_name} is not allowed for password external accounts.",
                )
        return
    if _has_password_field_content(payload.get("password")):
        raise ValidationError("password is not allowed for oauth2 external accounts.")


def _has_password_field_content(value: JSONValue) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _has_oauth_field_content(*, field_name: str, value: JSONValue) -> bool:
    if value is None:
        return False
    if field_name == "oauth_status":
        normalized = coerce_optional_trimmed_str(value)
        return normalized is not None and normalized != OAUTH_STATUS_NONE
    if field_name in {"oauth_scopes", "oauth_required_scopes"}:
        if not isinstance(value, list):
            return True
        return any(_has_password_field_content(item) for item in value)
    if field_name == "oauth_expires_at_ms":
        return True
    if isinstance(value, str):
        return bool(value.strip())
    return True


def validate_supported_external_account_fields(payload: JSONValue) -> None:
    if not is_json_dict(payload):
        raise ValidationError("external account payload must be an object.")
    validate_allowed_json_object_fields(
        payload,
        allowed_field_names=EXTERNAL_ACCOUNT_FIELD_NAMES,
        label="external account",
    )
