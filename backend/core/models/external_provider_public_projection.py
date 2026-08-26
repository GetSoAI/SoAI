"""SoAI - Safe external provider public projection [backend/core/models/external_provider_public_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models.external_provider_record import (
    ExternalProviderRecord,
    coerce_external_provider_internal_record,
)
from core.security.response_redaction import (
    REDACTED_PLACEHOLDER,
    redact_response_payload,
)
from core.serialization.json import normalize_for_json
from core.types.json_value import coerce_json_dict, coerce_str_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "coerce_external_provider_record",
    "sanitize_provider_audit",
)


def coerce_external_provider_record(
    value: JSONDict,
    *,
    label: str,
) -> ExternalProviderRecord:
    internal = coerce_external_provider_internal_record(value, label=label)
    record: ExternalProviderRecord = {**internal}
    if "api_key" in record:
        record["api_key"] = REDACTED_PLACEHOLDER
    if "extra_headers" in record:
        redacted_headers_value = redact_response_payload(record["extra_headers"])
        redacted_headers = coerce_str_dict(redacted_headers_value)
        if redacted_headers is not None:
            record["extra_headers"] = redacted_headers
    if "extra_query_params" in record:
        redacted_query_value = redact_response_payload(record["extra_query_params"])
        redacted_query = coerce_str_dict(redacted_query_value)
        if redacted_query is not None:
            record["extra_query_params"] = redacted_query
    return record


def sanitize_provider_audit[T](details: T, _details_type: type[T] | None = None) -> JSONDict:
    _ = _details_type
    normalized = normalize_for_json(details)
    redacted = redact_response_payload(normalized)
    sanitized = coerce_json_dict(redacted)
    if sanitized is None:
        return {}
    sanitized.pop("api_key", None)
    return sanitized
