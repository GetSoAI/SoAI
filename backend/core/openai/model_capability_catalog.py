"""SoAI - Enriched internal model capability catalog contract [backend/core/openai/model_capability_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence

from core.errors.exceptions import ValidationError
from core.openai.models_payloads import (
    project_openai_model_object,
    require_openai_model_list_entries,
)
from core.types.json import JSONDict, JSONValue
from core.types.json_value import copy_json_dict, require_json_dict
from core.validation.object_fields import require_exact_json_fields
from core.validation.record_fields import require_str_list
from core.validation.strict_numbers import require_positive_int_strict

__all__ = (
    "build_model_capability_catalog_entry",
    "build_model_capability_catalog_payload",
    "build_model_capability_catalog_response",
)

MODEL_CAPABILITY_CATALOG_FIELDS = frozenset(
    {
        "id",
        "object",
        "created",
        "owned_by",
        "context_window_tokens",
        "modalities",
        "openai_capabilities",
    },
)


def _require_optional_context_window(
    value: JSONValue,
    *,
    context: str,
) -> int | None:
    if value is None:
        return None
    return require_positive_int_strict(
        value,
        error_message=f"{context} field 'context_window_tokens' must be a positive integer.",
    )


def _require_optional_modalities(value: JSONValue, *, context: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValidationError(f"{context} field 'modalities' must be a non-empty string array.")
    return require_str_list(
        value,
        label=f"{context} field 'modalities'",
        build_error=ValidationError,
        invalid_message=f"{context} field 'modalities' must not be empty.",
        entry_message=f"{context} field 'modalities' must contain only non-empty strings.",
    )


def _require_optional_capabilities(value: JSONValue, *, context: str) -> JSONDict | None:
    if value is None:
        return None
    try:
        capabilities = require_json_dict(value, label=f"{context}.openai_capabilities")
    except ValidationError as exception:
        raise ValidationError(
            f"{context} field 'openai_capabilities' must be a JSON object.",
        ) from exception
    return copy_json_dict(capabilities)


def build_model_capability_catalog_entry(entry: JSONValue, *, context: str) -> JSONDict:
    if not isinstance(entry, dict):
        raise ValidationError(f"{context} must be an object.")
    require_exact_json_fields(
        entry,
        allowed_fields=MODEL_CAPABILITY_CATALOG_FIELDS,
        label=context,
    )
    result = project_openai_model_object(entry, context=context)
    context_window_tokens = _require_optional_context_window(
        entry.get("context_window_tokens"),
        context=context,
    )
    if context_window_tokens is not None:
        result["context_window_tokens"] = context_window_tokens
    modalities = _require_optional_modalities(entry.get("modalities"), context=context)
    if modalities is not None:
        result["modalities"] = modalities
    capabilities = _require_optional_capabilities(
        entry.get("openai_capabilities"),
        context=context,
    )
    if capabilities is not None:
        result["openai_capabilities"] = capabilities
    return result


def build_model_capability_catalog_response(raw: JSONValue) -> JSONDict:
    entries = require_openai_model_list_entries(raw)
    return build_model_capability_catalog_payload(entries)


def build_model_capability_catalog_payload(entries: Sequence[JSONValue]) -> JSONDict:
    models: list[JSONDict] = []
    for entry in entries:
        models.append(
            build_model_capability_catalog_entry(
                entry,
                context="OpenAI model capability catalog entry",
            ),
        )
    return {"object": "list", "data": models}
