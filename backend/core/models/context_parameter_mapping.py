"""SoAI - Context window parameter name and key mapping [backend/core/models/context_parameter_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.context_window import (
    MODEL_PARAM_STANDARDIZED_NAME,
    PARAMETER_SEMANTIC_ROLE_CONTEXT_WINDOW,
    coerce_positive_context_tokens,
    resolve_semantic_parameter_name,
)
from core.types.json import is_json_dict
from core.types.json_value import copy_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "map_standardized_context_keys",
    "map_standardized_context_updates",
    "resolve_context_parameter_name",
)

FIT_CONTEXT_PARAMETER_NAME = "fit_ctx"


def resolve_context_parameter_name(schema: JSONDict) -> str | None:
    normalized_schema: dict[str, JSONDict] = {
        key: definition
        for key, definition in schema.items()
        if isinstance(key, str) and is_json_dict(definition)
    }
    return resolve_semantic_parameter_name(
        normalized_schema,
        PARAMETER_SEMANTIC_ROLE_CONTEXT_WINDOW,
    )


def map_standardized_context_updates(
    parameters: JSONDict,
    context_parameter_name: str | None,
    schema: JSONDict,
) -> JSONDict:
    mapped: JSONDict = {}
    has_standardized_key = MODEL_PARAM_STANDARDIZED_NAME in parameters
    canonical_context_value: JSONValue | None = None
    if context_parameter_name and has_standardized_key:
        standardized_value = parameters.get(MODEL_PARAM_STANDARDIZED_NAME)
        context_tokens = coerce_positive_context_tokens(standardized_value)
        if context_tokens is None:
            raise ValidationError(
                f"'{MODEL_PARAM_STANDARDIZED_NAME}' must be a positive integer.",
            )
        definition = schema.get(context_parameter_name)
        schema_type = definition.get("type") if is_json_dict(definition) else None
        if schema_type == "integer":
            canonical_context_value = context_tokens
        elif schema_type == "string":
            canonical_context_value = str(context_tokens)
        else:
            raise ValidationError(
                f"Context parameter '{context_parameter_name}' must declare integer or string type.",
            )
        if context_parameter_name in parameters:
            backend_value = parameters.get(context_parameter_name)
            backend_tokens = coerce_positive_context_tokens(backend_value)
            if backend_tokens is None:
                raise ValidationError(
                    f"Conflicting context window values provided for '{MODEL_PARAM_STANDARDIZED_NAME}' and '{context_parameter_name}'.",
                )
            canonical_backend_value: JSONValue = (
                backend_tokens if schema_type == "integer" else str(backend_tokens)
            )
            if canonical_backend_value != canonical_context_value:
                raise ValidationError(
                    f"Conflicting context window values provided for '{MODEL_PARAM_STANDARDIZED_NAME}' and '{context_parameter_name}'.",
                )
    for key, value in parameters.items():
        if context_parameter_name and key == MODEL_PARAM_STANDARDIZED_NAME:
            if canonical_context_value is not None:
                mapped[context_parameter_name] = copy_json_value(canonical_context_value)
            continue
        if context_parameter_name and key == context_parameter_name and has_standardized_key:
            continue
        mapped[key] = copy_json_value(value)
    if context_parameter_name and (
        MODEL_PARAM_STANDARDIZED_NAME in parameters or context_parameter_name in parameters
    ):
        context_value = mapped.get(context_parameter_name)
        if FIT_CONTEXT_PARAMETER_NAME in schema and FIT_CONTEXT_PARAMETER_NAME not in parameters:
            mapped[FIT_CONTEXT_PARAMETER_NAME] = copy_json_value(context_value)
    return mapped


def map_standardized_context_keys(
    keys: list[str],
    context_parameter_name: str | None,
    schema: JSONDict,
) -> list[str]:
    mapped: list[str] = []
    for key in keys:
        mapped_key = (
            context_parameter_name
            if context_parameter_name and key == MODEL_PARAM_STANDARDIZED_NAME
            else key
        )
        if mapped_key in mapped:
            continue
        mapped.append(mapped_key)
    if (
        context_parameter_name
        and FIT_CONTEXT_PARAMETER_NAME in schema
        and (MODEL_PARAM_STANDARDIZED_NAME in keys or context_parameter_name in keys)
        and FIT_CONTEXT_PARAMETER_NAME not in mapped
    ):
        mapped.append(FIT_CONTEXT_PARAMETER_NAME)
    return mapped
