"""SoAI - Provider mutation field validation [backend/database/repositories/plugins/provider_mutation_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal, overload

from cryptography.fernet import Fernet

from core.errors.exceptions import StateError, ValidationError
from core.models.external_provider_record import normalize_external_provider_name
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.security.encryption import encrypt_data
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict, JSONValue
from core.validation.epoch import require_unix_epoch_ms
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_positive_int_strict,
)
from core.validation.strings import require_canonical_trimmed_json_text
from database.core.sqlite_values import SQLiteValue

__all__ = (
    "PROVIDER_UPDATE_FIELDS",
    "normalize_provider_updates",
    "require_expected_provider_revision",
    "require_provider_mutation_metadata",
    "require_provider_validation_state",
)

PROVIDER_UPDATE_FIELDS = (
    "name",
    "api_url",
    "api_key",
    "models_filter",
    "context_window_tokens",
    "extra_headers",
    "extra_query_params",
)
_VALIDATION_STATUSES = frozenset(
    {"AUTH_REQUIRED", "ERROR", "OK", "TIMEOUT", "UNCHECKED", "VALIDATING"}
)


def require_expected_provider_revision(value: int) -> int:
    return require_non_negative_int_strict(
        value,
        error_message="expected_revision must be a non-negative integer.",
    )


@overload
def require_provider_validation_state(
    status: str,
    error: str | None,
    validated_at_ms: int,
) -> tuple[str, str | None, int]: ...


@overload
def require_provider_validation_state(
    status: str,
    error: str | None,
    validated_at_ms: Literal[None],
) -> tuple[str, str | None, Literal[None]]: ...


def require_provider_validation_state(
    status: str,
    error: str | None,
    validated_at_ms: int | None,
) -> tuple[str, str | None, int | None]:
    if not isinstance(status, str) or status not in _VALIDATION_STATUSES:
        raise ValidationError("Provider validation status is invalid.")
    if error is not None and (not isinstance(error, str) or not error.strip()):
        raise ValidationError("Provider validation error must be a non-empty string or null.")
    if validated_at_ms is not None:
        require_unix_epoch_ms(
            validated_at_ms,
            error_message="Provider validation time must be an epoch-millisecond integer or null.",
        )
    return (status, error.strip() if error is not None else None, validated_at_ms)


def require_provider_mutation_metadata(
    owner_id: str,
    plugin_name: str,
    provider_id: str,
    accepted_at_ms: int,
) -> None:
    require_canonical_trimmed_json_text(
        owner_id,
        error_message="Provider mutation owner_id is invalid.",
    )
    require_portable_plugin_identifier(plugin_name, field_name="plugin_name")
    require_canonical_trimmed_json_text(
        provider_id,
        error_message="Provider mutation provider_id is invalid.",
    )
    require_unix_epoch_ms(
        accepted_at_ms,
        error_message="Provider mutation requires a valid server time.",
    )


def _require_string_mapping(value: JSONValue, field_name: str) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationError(f"{field_name} must be an object or null.")
    normalized: dict[str, str] = {}
    for key, entry in value.items():
        if not isinstance(key, str) or not key or not isinstance(entry, str):
            raise ValidationError(f"{field_name} must contain string keys and values.")
        normalized[key] = entry
    return normalized


def normalize_provider_updates(
    updates: JSONDict,
    fernet: tuple[Fernet, ...] | None = None,
) -> dict[str, SQLiteValue]:
    if not updates:
        raise ValidationError("Provider update must include at least one field.")
    invalid_fields = set(updates) - set(PROVIDER_UPDATE_FIELDS)
    if invalid_fields:
        raise ValidationError(
            f"Provider update contains unsupported fields: {sorted(invalid_fields)}"
        )
    normalized: dict[str, SQLiteValue] = {}
    for field_name in PROVIDER_UPDATE_FIELDS:
        if field_name not in updates:
            continue
        value = updates[field_name]
        if field_name in {"name", "api_url"}:
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{field_name} must be a non-empty string.")
            normalized[field_name] = value.strip()
            if field_name == "name":
                canonical_name = normalize_external_provider_name(value)
                if canonical_name is None:
                    raise ValidationError("name must be a non-empty string.")
                normalized["canonical_name"] = canonical_name
        elif field_name == "api_key":
            if value is not None and not isinstance(value, str):
                raise ValidationError("api_key must be a string or null.")
            if value:
                if not fernet:
                    raise StateError("Provider API key encryption owner is unavailable.")
                normalized[field_name] = encrypt_data(fernet, value)
            else:
                normalized[field_name] = None
        elif field_name == "models_filter":
            if value is not None and (
                not isinstance(value, list) or any(not isinstance(entry, str) for entry in value)
            ):
                raise ValidationError("models_filter must be an array of strings or null.")
            normalized[field_name] = (
                serialize_json_compact_stable_strict(value) if value is not None else None
            )
        elif field_name == "context_window_tokens":
            normalized[field_name] = (
                require_positive_int_strict(
                    value,
                    error_message="context_window_tokens must be a positive integer or null.",
                )
                if value is not None
                else None
            )
        else:
            mapping = _require_string_mapping(value, field_name)
            normalized[field_name] = (
                serialize_json_compact_stable_strict(mapping) if mapping is not None else None
            )
    return normalized
