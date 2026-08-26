"""SoAI - External provider response record normalization [backend/core/models/external_provider_record.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import unicodedata
from typing import TYPE_CHECKING, TypedDict

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_str_dict, coerce_str_list
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ExternalProviderRecord",
    "ExternalProviderInternalRecord",
    "build_external_provider_id",
    "coerce_external_provider_internal_record",
    "normalize_external_provider_name",
)

_EXTERNAL_PROVIDER_STATUS_VALUES: frozenset[str] = frozenset(
    {"UNCHECKED", "OK", "ERROR", "TIMEOUT", "VALIDATING", "AUTH_REQUIRED"},
)


class ProviderRecordFields(TypedDict, total=False):
    name: str | None
    api_url: str
    api_key: str | None
    models_filter: list[str]
    extra_headers: dict[str, str]
    extra_query_params: dict[str, str]
    context_window_tokens: int
    created_at_ms: int
    last_status: str
    last_error: str | None
    last_checked_at_ms: int | None


class ExternalProviderRecord(ProviderRecordFields):
    id: str
    plugin_name: str
    revision: int


class ExternalProviderInternalRecord(ProviderRecordFields):
    id: str
    plugin_name: str
    revision: int


def normalize_external_provider_name(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        return None
    return normalized.casefold()


def build_external_provider_id(plugin_name: str, api_url: str) -> str:
    token = f"{plugin_name}:{api_url}".encode()
    return f"prov{hashlib.sha256(token).hexdigest()[:16]}"


def _required_nonempty_str_field(value: JSONDict, field: str, label: str) -> str:
    field_value = value.get(field)
    if isinstance(field_value, str) and field_value.strip():
        return field_value.strip()
    raise ValidationError(f"{label} field '{field}' is invalid.")


def _optional_name_field(value: JSONDict, label: str) -> tuple[bool, str | None]:
    field_value = value.get("name")
    if isinstance(field_value, str):
        return (True, field_value.strip() or None)
    if field_value is None:
        return (False, None)
    raise ValidationError(f"{label} field 'name' is invalid.")


def _optional_nonempty_str_field(
    value: JSONDict,
    field: str,
    label: str,
) -> tuple[bool, str]:
    field_value = value.get(field)
    if isinstance(field_value, str) and field_value.strip():
        return (True, field_value.strip())
    if field_value is None:
        return (False, "")
    raise ValidationError(f"{label} field '{field}' is invalid.")


def _optional_str_field(
    value: JSONDict,
    field: str,
    label: str,
) -> tuple[bool, str]:
    field_value = value.get(field)
    if isinstance(field_value, str):
        return (True, field_value)
    if field_value is None:
        return (False, "")
    raise ValidationError(f"{label} field '{field}' is invalid.")


def _optional_str_list_field(
    value: JSONDict,
    field: str,
    label: str,
) -> tuple[bool, list[str]]:
    field_value = value.get(field)
    coerced_value = coerce_str_list(field_value)
    if coerced_value is not None:
        return (True, coerced_value)
    if field_value is None:
        return (False, [])
    raise ValidationError(f"{label} field '{field}' is invalid.")


def _optional_str_dict_field(
    value: JSONDict,
    field: str,
    label: str,
) -> tuple[bool, dict[str, str]]:
    field_value = value.get(field)
    coerced_value = coerce_str_dict(field_value)
    if coerced_value is not None:
        return (True, coerced_value)
    if field_value is None:
        return (False, {})
    raise ValidationError(f"{label} field '{field}' is invalid.")


def _optional_int_field(
    value: JSONDict,
    field: str,
    label: str,
) -> tuple[bool, int]:
    field_value = value.get(field)
    if is_strict_int(field_value):
        return (True, field_value)
    if field_value is None:
        return (False, 0)
    raise ValidationError(f"{label} field '{field}' is invalid.")


def _required_nonnegative_int_field(value: JSONDict, field: str, label: str) -> int:
    field_value = value.get(field)
    if is_strict_int(field_value) and field_value >= 0:
        return field_value
    raise ValidationError(f"{label} field '{field}' is invalid.")


def _optional_status_field(value: JSONDict, label: str) -> tuple[bool, str]:
    field_value = value.get("last_status")
    if isinstance(field_value, str) and field_value.strip():
        normalized_status = field_value.strip()
        if normalized_status in _EXTERNAL_PROVIDER_STATUS_VALUES:
            return (True, normalized_status)
        raise ValidationError(f"{label} field 'last_status' is invalid.")
    if field_value is None:
        return (False, "")
    raise ValidationError(f"{label} field 'last_status' is invalid.")


def _apply_common_provider_fields(
    record: ProviderRecordFields,
    value: JSONDict,
    label: str,
) -> None:
    name_present, name = _optional_name_field(value, label)
    if name_present:
        record["name"] = name
    api_url_present, api_url = _optional_nonempty_str_field(value, "api_url", label)
    if api_url_present:
        record["api_url"] = api_url
    models_filter_present, models_filter = _optional_str_list_field(
        value,
        "models_filter",
        label,
    )
    if models_filter_present:
        record["models_filter"] = models_filter
    created_at_ms_present, created_at_ms = _optional_int_field(
        value,
        "created_at_ms",
        label,
    )
    if created_at_ms_present:
        record["created_at_ms"] = created_at_ms
    last_status_present, last_status = _optional_status_field(value, label)
    if last_status_present:
        record["last_status"] = last_status
    last_error_present, last_error = _optional_str_field(value, "last_error", label)
    if last_error_present:
        record["last_error"] = last_error
    last_checked_at_ms_present, last_checked_at_ms = _optional_int_field(
        value,
        "last_checked_at_ms",
        label,
    )
    if last_checked_at_ms_present:
        record["last_checked_at_ms"] = last_checked_at_ms
    context_window_tokens_present, context_window_tokens = _optional_int_field(
        value,
        "context_window_tokens",
        label,
    )
    if context_window_tokens_present:
        if context_window_tokens < 1:
            raise ValidationError(f"{label} field 'context_window_tokens' is invalid.")
        record["context_window_tokens"] = context_window_tokens


def coerce_external_provider_internal_record(
    value: JSONDict,
    *,
    label: str,
) -> ExternalProviderInternalRecord:
    record: ExternalProviderInternalRecord = {
        "id": _required_nonempty_str_field(value, "id", label),
        "plugin_name": _required_nonempty_str_field(value, "plugin_name", label),
        "revision": _required_nonnegative_int_field(value, "revision", label),
    }
    _apply_common_provider_fields(record, value, label)
    api_key_present, api_key = _optional_str_field(value, "api_key", label)
    if api_key_present:
        record["api_key"] = api_key
    extra_headers_present, extra_headers = _optional_str_dict_field(
        value,
        "extra_headers",
        label,
    )
    if extra_headers_present:
        record["extra_headers"] = extra_headers
    extra_query_params_present, extra_query_params = _optional_str_dict_field(
        value,
        "extra_query_params",
        label,
    )
    if extra_query_params_present:
        record["extra_query_params"] = extra_query_params
    return record
