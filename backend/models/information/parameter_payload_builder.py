"""SoAI - Model formatted parameter payload builder [backend/models/information/parameter_payload_builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError, NotFoundError
from core.models.context_window import (
    MODEL_PARAM_STANDARDIZED_NAME,
    PARAMETER_SEMANTIC_ROLE_CONTEXT_WINDOW,
    build_standardized_context_display_name,
    resolve_semantic_parameter_name,
)
from core.models.source_identifier import require_source_model_id
from core.types.json import is_json_dict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from models.information.dependencies import ModelInformationServiceDependencies

__all__ = ("build_formatted_parameters_payload",)


def _definition_has_default(definition: JSONDict) -> bool:
    has_default_field = definition.get("has_default")
    if has_default_field is not None:
        return bool(has_default_field)
    return "default" in definition


def _coerce_parameter_version(model_info: JSONDict) -> int:
    raw_value = model_info.get("parameter_version", 0)
    if isinstance(raw_value, bool):
        return 0
    return raw_value if isinstance(raw_value, int) else 0


async def build_formatted_parameters_payload(
    *,
    deps: ModelInformationServiceDependencies,
    universal_id: str,
    model_get_info: Callable[[str], Awaitable[JSONDict | None]],
) -> JSONDict:
    model_info = await model_get_info(universal_id)
    if not model_info:
        raise NotFoundError(
            f"Model '{universal_id}' not found.",
            details={"universal_id": universal_id},
        )
    plugin_name = coerce_optional_trimmed_str(model_info.get("plugin"))
    if not plugin_name:
        raise ConfigurationError(
            f"Model '{universal_id}' has invalid plugin metadata.",
            details={"universal_id": universal_id},
        )
    if not deps.plugin_manager.is_known_plugin(plugin_name):
        display_name = await deps.plugin_manager.get_plugin_display_name(plugin_name)
        raise ConfigurationError(
            f"Plugin '{display_name}' for model '{universal_id}' is not recognized.",
            details={"plugin": plugin_name, "universal_id": universal_id},
        )
    source_model_id = require_source_model_id(model_info)
    (schema, categories), overrides = await asyncio.gather(
        deps.param_manager.get_parameter_schema_snapshot(plugin_name),
        deps.database_models.get_model_custom_parameters(universal_id),
        return_exceptions=False,
    )
    schema_definitions: dict[str, JSONDict] = (
        {
            name: definition
            for name, definition in schema.items()
            if isinstance(name, str) and is_json_dict(definition)
        }
        if isinstance(schema, dict)
        else {}
    )
    effective_values = {
        **{
            name: definition.get("default")
            for name, definition in schema_definitions.items()
            if _definition_has_default(definition)
        },
        **overrides,
    }
    context_parameter_name = resolve_semantic_parameter_name(
        schema_definitions,
        PARAMETER_SEMANTIC_ROLE_CONTEXT_WINDOW,
    )
    parameters_payload: JSONDict = {}
    for name, definition in schema_definitions.items():
        definition_payload = dict(definition)
        if context_parameter_name and name == context_parameter_name:
            definition_payload["display_name"] = build_standardized_context_display_name(name)
            if name != MODEL_PARAM_STANDARDIZED_NAME:
                definition_payload["linked_parameter_name"] = MODEL_PARAM_STANDARDIZED_NAME
        parameters_payload[name] = {
            "definition": definition_payload,
            "current_value": effective_values.get(name, definition.get("default")),
            "is_custom": name in overrides,
            "has_default": _definition_has_default(definition),
        }
    if context_parameter_name and context_parameter_name != MODEL_PARAM_STANDARDIZED_NAME:
        context_definition = schema_definitions.get(context_parameter_name)
        if context_definition is not None:
            aliases_value = context_definition.get("aliases")
            aliases = list(aliases_value) if isinstance(aliases_value, list) else []
            if context_parameter_name not in aliases:
                aliases.append(context_parameter_name)
            standardized_definition = dict(context_definition)
            standardized_definition["aliases"] = aliases
            standardized_definition["display_name"] = MODEL_PARAM_STANDARDIZED_NAME
            standardized_definition["linked_parameter_name"] = context_parameter_name
            standardized_definition["semantic_role"] = PARAMETER_SEMANTIC_ROLE_CONTEXT_WINDOW
            standardized_definition["is_standardized_alias"] = True
            parameters_payload[MODEL_PARAM_STANDARDIZED_NAME] = {
                "definition": standardized_definition,
                "current_value": effective_values.get(
                    context_parameter_name,
                    context_definition.get("default"),
                ),
                "is_custom": context_parameter_name in overrides,
                "has_default": _definition_has_default(context_definition),
            }
    return {
        "universal_id": universal_id,
        "plugin": plugin_name,
        "source_model_id": source_model_id,
        "parameter_version": _coerce_parameter_version(model_info),
        "parameters": parameters_payload,
        "categories": categories,
    }
