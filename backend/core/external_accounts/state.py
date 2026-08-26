"""SoAI - External account state and scope helpers [backend/core/external_accounts/state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import NoReturn

from core.errors.exceptions import StateError, ValidationError
from core.oauth.types import OAuthError, OAuthErrorCode
from core.types.json import JSONValue
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_non_empty_str
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "AUTH_TYPE_OAUTH2",
    "AUTH_TYPE_FORM_CREDENTIAL",
    "OAUTH_STATUS_AUTH_REQUIRED",
    "OAUTH_STATUS_ERROR",
    "OAUTH_STATUS_EXPIRED",
    "OAUTH_STATUS_INSUFFICIENT_SCOPE",
    "OAUTH_STATUS_NONE",
    "OAUTH_STATUS_READY",
    "coerce_oauth_status",
    "is_external_account_ready",
    "normalize_oauth_status",
    "optional_oauth_status",
    "parse_scope_text",
    "raise_for_oauth_status",
    "read_scope_field",
    "require_auth_type",
    "require_oauth2_account",
    "resolve_effective_oauth_status",
    "resolve_oauth_grant_status",
)

AUTH_TYPE_FORM_CREDENTIAL = "password"
AUTH_TYPE_OAUTH2 = "oauth2"
OAUTH_STATUS_NONE = "none"
OAUTH_STATUS_READY = "ready"
OAUTH_STATUS_AUTH_REQUIRED = "auth_required"
OAUTH_STATUS_INSUFFICIENT_SCOPE = "insufficient_scope"
OAUTH_STATUS_EXPIRED = "expired"
OAUTH_STATUS_ERROR = "error"
_ALLOWED_OAUTH_STATUS_VALUES: frozenset[str] = frozenset(
    {
        OAUTH_STATUS_NONE,
        OAUTH_STATUS_READY,
        OAUTH_STATUS_AUTH_REQUIRED,
        OAUTH_STATUS_INSUFFICIENT_SCOPE,
        OAUTH_STATUS_EXPIRED,
        OAUTH_STATUS_ERROR,
    },
)


def require_auth_type(value: JSONValue) -> str:
    normalized = require_non_empty_str(
        value,
        label="auth_type",
        build_error=ValidationError,
        invalid_message="auth_type is required.",
    )
    if normalized not in {AUTH_TYPE_FORM_CREDENTIAL, AUTH_TYPE_OAUTH2}:
        raise ValidationError("auth_type must be password or oauth2.")
    return normalized


def coerce_oauth_status(value: JSONValue | None) -> str:
    if not isinstance(value, str):
        raise ValidationError("oauth_status must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValidationError("oauth_status must not be empty.")
    if normalized not in _ALLOWED_OAUTH_STATUS_VALUES:
        raise ValidationError(
            "oauth_status must be one of: none, ready, auth_required, insufficient_scope, expired, error.",
        )
    return normalized


def optional_oauth_status(value: JSONValue | None) -> str:
    if value is None:
        return OAUTH_STATUS_NONE
    return coerce_oauth_status(value)


def normalize_oauth_status(value: JSONValue | None) -> str:
    try:
        return optional_oauth_status(value)
    except ValidationError as exception:
        raise StateError("oauth_status is invalid.") from exception


def parse_scope_text(value: str | None) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    normalized_scopes: list[str] = []
    for entry in value.split(" "):
        scope = entry.strip()
        if not scope or scope in normalized_scopes:
            continue
        normalized_scopes.append(scope)
    return tuple(normalized_scopes)


def read_scope_field(value: JSONValue, *, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValidationError(f"{label} must be a list of strings or null.")
    normalized_scopes: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise ValidationError(f"{label} must be a list of strings or null.")
        scope = entry.strip()
        if not scope or scope in normalized_scopes:
            continue
        normalized_scopes.append(scope)
    return tuple(normalized_scopes)


def resolve_oauth_grant_status(
    *,
    required_scopes: Sequence[str],
    granted_scopes: Sequence[str],
) -> str:
    required_scope_set = {scope for scope in required_scopes if scope}
    if not required_scope_set:
        return OAUTH_STATUS_READY
    granted_scope_set = {scope for scope in granted_scopes if scope}
    if required_scope_set.issubset(granted_scope_set):
        return OAUTH_STATUS_READY
    return OAUTH_STATUS_INSUFFICIENT_SCOPE


def resolve_effective_oauth_status(
    *,
    oauth_status: JSONValue | None,
    oauth_expires_at_ms: JSONValue,
    has_refresh_token: bool,
    now_ms: int,
) -> str:
    normalized_status = normalize_oauth_status(oauth_status)
    if normalized_status != OAUTH_STATUS_READY:
        return normalized_status
    if has_refresh_token:
        return normalized_status
    if oauth_expires_at_ms is None:
        return normalized_status
    if not is_strict_int(oauth_expires_at_ms):
        raise StateError("timestamp value is invalid.")
    if oauth_expires_at_ms <= now_ms:
        return OAUTH_STATUS_EXPIRED
    return normalized_status


def is_external_account_ready(
    *,
    auth_type: str,
    has_password: bool,
    oauth_status: str,
) -> bool:
    if auth_type == AUTH_TYPE_FORM_CREDENTIAL:
        return has_password
    if auth_type == AUTH_TYPE_OAUTH2:
        return oauth_status == OAUTH_STATUS_READY
    return False


def raise_for_oauth_status(status: str) -> NoReturn:
    if status == OAUTH_STATUS_INSUFFICIENT_SCOPE:
        raise OAuthError(
            OAuthErrorCode.INSUFFICIENT_SCOPE,
            "External account OAuth scopes are insufficient.",
        )
    if status == OAUTH_STATUS_EXPIRED:
        raise OAuthError(
            OAuthErrorCode.AUTH_REQUIRED,
            "External account OAuth has expired.",
        )
    if status == OAUTH_STATUS_ERROR:
        raise OAuthError(
            OAuthErrorCode.TOKEN_REFRESH_FAILED,
            "External account OAuth is in an error state.",
        )
    raise OAuthError(OAuthErrorCode.AUTH_REQUIRED, "External account OAuth is not ready.")


def require_oauth2_account(account: dict[str, JSONValue]) -> None:
    if coerce_optional_trimmed_str(account.get("auth_type")) != AUTH_TYPE_OAUTH2:
        raise ValidationError("OAuth is only supported for oauth2 accounts.")
