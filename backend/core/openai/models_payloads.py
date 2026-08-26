"""SoAI - Strict public OpenAI model response projection [backend/core/openai/models_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue
from core.validation.object_fields import require_exact_json_fields
from core.validation.strict_numbers import require_non_negative_int_strict
from core.validation.strings import coerce_required_non_empty_str

__all__ = (
    "OpenAIModelListResponse",
    "OpenAIModelObject",
    "project_openai_model_list_response",
    "project_openai_model_object",
    "require_openai_model_list_entries",
)

OPENAI_MODEL_LIST_FIELDS = frozenset({"object", "data"})

OpenAIModelObject = JSONDict
OpenAIModelListResponse = JSONDict


def _require_nonempty_str(value: JSONValue, *, field_name: str, context: str) -> str:
    return coerce_required_non_empty_str(
        value,
        label=f"{context} field '{field_name}'",
    )


def project_openai_model_object(entry: JSONValue, *, context: str) -> JSONDict:
    if not isinstance(entry, dict):
        raise ValidationError(f"{context} must be an object.")
    model_id = _require_nonempty_str(entry.get("id"), field_name="id", context=context)
    if entry.get("object") != "model":
        raise ValidationError(f"{context} field 'object' must equal 'model'.")
    created = require_non_negative_int_strict(
        entry.get("created"),
        error_message=f"{context} field 'created' must be a non-negative integer.",
    )
    owned_by = _require_nonempty_str(entry.get("owned_by"), field_name="owned_by", context=context)
    return {
        "id": model_id,
        "object": "model",
        "created": created,
        "owned_by": owned_by,
    }


def require_openai_model_list_entries(raw: JSONValue) -> list[JSONValue]:
    if not isinstance(raw, dict):
        raise ValidationError("OpenAI model list payload must be an object.")
    require_exact_json_fields(
        raw,
        allowed_fields=OPENAI_MODEL_LIST_FIELDS,
        label="OpenAI model list payload",
    )
    if raw.get("object") != "list":
        raise ValidationError("OpenAI model list payload must have object='list'.")
    data_value = raw.get("data")
    if not isinstance(data_value, list):
        raise ValidationError("OpenAI model list payload must have a 'data' array.")
    return list(data_value)


def project_openai_model_list_response(raw: JSONValue) -> JSONDict:
    models: list[JSONDict] = []
    for entry in require_openai_model_list_entries(raw):
        models.append(
            project_openai_model_object(entry, context="OpenAI model list entry"),
        )
    return {"object": "list", "data": models}
