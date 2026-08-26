"""SoAI - Shared external account payload helpers [backend/features/external_accounts/account_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.external_accounts.field_names import (
    EXTERNAL_ACCOUNT_OAUTH_CONFIGURATION_FIELD_NAMES,
)
from core.types.json import JSONDict, JSONValue, is_json_dict
from core.validation.json_object_fields import (
    extract_known_json_object_fields,
    require_optional_json_object_section,
    validate_allowed_json_object_fields,
)

__all__ = (
    "extract_external_account_payload",
    "extract_external_account_updates",
)

_ROOT_FIELDS: tuple[str, ...] = ("label", "username", "auth", "transport")
_AUTH_FIELDS: tuple[str, ...] = ("type", "password", "oauth")
_OAUTH_PUBLIC_FIELDS: tuple[str, ...] = (
    "status",
    "client_id",
    "client_secret",
    "resource_metadata_url",
    "auth_server_issuer",
    "authorization_endpoint",
    "token_endpoint",
    "registration_endpoint",
    "token_endpoint_auth_method",
    "scopes",
    "required_scopes",
)


def extract_external_account_payload(payload: JSONDict) -> JSONDict:
    return _extract_known_fields(payload)


def extract_external_account_updates(payload: JSONDict) -> JSONDict:
    return _extract_known_fields(payload)


def _extract_known_fields(payload: JSONDict) -> JSONDict:
    validate_allowed_json_object_fields(
        payload,
        allowed_field_names=_ROOT_FIELDS,
        label="external account payload",
    )
    extracted = extract_known_json_object_fields(payload, ("label", "username"))
    auth_value = require_optional_json_object_section(payload, section_name="auth")
    if auth_value is None:
        return extracted
    validate_allowed_json_object_fields(
        auth_value,
        allowed_field_names=_AUTH_FIELDS,
        label="auth",
    )
    extracted["auth_type"] = auth_value.get("type")
    if "password" in auth_value:
        extracted["password"] = auth_value.get("password")
    oauth_value = _require_optional_auth_oauth_dict(auth_value)
    if oauth_value is None:
        return extracted
    validate_allowed_json_object_fields(
        oauth_value,
        allowed_field_names=_OAUTH_PUBLIC_FIELDS,
        label="auth.oauth",
    )
    for field_name in EXTERNAL_ACCOUNT_OAUTH_CONFIGURATION_FIELD_NAMES:
        public_field_name = field_name.removeprefix("oauth_")
        if public_field_name not in oauth_value:
            continue
        field_value = oauth_value.get(public_field_name)
        if field_name == "oauth_status":
            extracted[field_name] = _normalize_public_oauth_status(field_value)
            continue
        extracted[field_name] = field_value
    return extracted


def _normalize_public_oauth_status(value: JSONValue) -> str:
    if not isinstance(value, str):
        raise ValidationError("auth.oauth.status must be 'none'.")
    normalized = value.strip()
    if normalized != "none":
        raise ValidationError("auth.oauth.status must be 'none'.")
    return normalized


def _require_optional_auth_oauth_dict(auth_value: JSONDict) -> JSONDict | None:
    oauth_value = auth_value.get("oauth")
    if oauth_value is None:
        return None
    if not is_json_dict(oauth_value):
        raise ValidationError("auth.oauth must be an object.")
    return oauth_value
