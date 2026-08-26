"""SoAI - Atomic parameter registration candidate construction [backend/models/parameters/registration_candidate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from core.errors.exceptions import StateError
from core.models.parameter_schema_document import validate_parameter_schema_document
from core.types.json import is_json_dict
from core.types.json_value import copy_json_dict
from core.validation.identifiers import collapse_identifier

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ParameterRegistrationCandidate",
    "ParameterInfo",
    "build_parameter_registration_candidate",
)


class ParameterInfo(TypedDict):
    definition: JSONDict
    cli_name: str


@dataclass(frozen=True, slots=True)
class ParameterRegistrationCandidate:
    definitions: JSONDict
    categories: JSONDict
    cache: dict[str, ParameterInfo]


def _build_parameter_cache(
    definitions: JSONDict,
) -> dict[str, ParameterInfo]:
    cache: dict[str, ParameterInfo] = {}
    info_by_name: dict[str, ParameterInfo] = {}
    for parameter_name, definition_value in definitions.items():
        if not is_json_dict(definition_value):
            raise StateError("Validated parameter definition became invalid.")
        normalized_key = collapse_identifier(parameter_name)
        cli_name_value = definition_value.get("cli_name")
        info: ParameterInfo = {
            "definition": definition_value,
            "cli_name": (
                cli_name_value.strip()
                if isinstance(cli_name_value, str)
                else f"--{parameter_name.replace('_', '-')}"
            ),
        }
        cache[normalized_key] = info
        info_by_name[parameter_name] = info
    for parameter_name, definition_value in definitions.items():
        if not is_json_dict(definition_value):
            raise StateError("Validated parameter definition became invalid.")
        aliases_value = definition_value.get("aliases", [])
        if not isinstance(aliases_value, list):
            raise StateError("Validated parameter aliases became invalid.")
        for alias in aliases_value:
            if not isinstance(alias, str):
                raise StateError("Validated parameter alias became invalid.")
            cache[collapse_identifier(alias)] = info_by_name[parameter_name]
    return cache


def build_parameter_registration_candidate(
    plugin_name: str,
    schema: JSONDict,
) -> ParameterRegistrationCandidate:
    validate_parameter_schema_document(plugin_name, schema)
    parameters_value = schema.get("parameters")
    if not is_json_dict(parameters_value):
        raise StateError("Validated parameter schema became invalid.")
    definitions = copy_json_dict(parameters_value)
    categories_value = schema.get("parameter_categories")
    categories = copy_json_dict(categories_value) if isinstance(categories_value, dict) else {}
    return ParameterRegistrationCandidate(
        definitions=definitions,
        categories=categories,
        cache=_build_parameter_cache(definitions),
    )
