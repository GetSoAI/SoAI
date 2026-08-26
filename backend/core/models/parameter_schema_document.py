"""SoAI - Shared V1 parameter schema document validation [backend/core/models/parameter_schema_document.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.parameter_schema_contract import validate_parameter_definitions
from core.types.json import is_json_dict
from core.validation.identifiers import collapse_identifier

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "declared_parameter_names",
    "validate_parameter_schema_document",
)


def _require_normalized_identifier(value: str, label: str) -> str:
    normalized = collapse_identifier(value)
    if not normalized:
        raise ValidationError(f"{label} must be a non-empty identifier.")
    return normalized


def _validate_parameter_identities(plugin_name: str, definitions: JSONDict) -> None:
    canonical_owner_by_key: dict[str, str] = {}
    semantic_owner_by_role: dict[str, str] = {}
    for parameter_name, definition_value in definitions.items():
        normalized_key = _require_normalized_identifier(
            parameter_name,
            f"Parameter name for plugin '{plugin_name}'",
        )
        existing_owner = canonical_owner_by_key.get(normalized_key)
        if existing_owner is not None:
            raise ValidationError(
                f"Plugin '{plugin_name}' parameters '{existing_owner}' and '{parameter_name}' collide.",
            )
        canonical_owner_by_key[normalized_key] = parameter_name
        if not is_json_dict(definition_value):
            raise ValidationError(
                f"Parameter '{parameter_name}' for plugin '{plugin_name}' must be an object.",
            )
        semantic_role_value = definition_value.get("semantic_role")
        if semantic_role_value is not None:
            if not isinstance(semantic_role_value, str) or not semantic_role_value.strip():
                raise ValidationError(
                    f"Parameter '{parameter_name}' for '{plugin_name}' has an invalid semantic role.",
                )
            normalized_role = semantic_role_value.strip().lower()
            semantic_owner = semantic_owner_by_role.get(normalized_role)
            if semantic_owner is not None:
                raise ValidationError(
                    f"Plugin '{plugin_name}' repeats semantic role '{normalized_role}'.",
                )
            semantic_owner_by_role[normalized_role] = parameter_name
        cli_name_value = definition_value.get("cli_name")
        if cli_name_value is not None and (
            not isinstance(cli_name_value, str) or not cli_name_value.strip()
        ):
            raise ValidationError(
                f"Parameter '{parameter_name}' for '{plugin_name}' has an invalid cli_name.",
            )

    alias_owner_by_key = dict(canonical_owner_by_key)
    for parameter_name, definition_value in definitions.items():
        if not is_json_dict(definition_value):
            raise ValidationError("Validated parameter definition became invalid.")
        aliases_value = definition_value.get("aliases", [])
        if not isinstance(aliases_value, list):
            raise ValidationError(
                f"Parameter '{parameter_name}' for '{plugin_name}' has invalid aliases.",
            )
        for alias in aliases_value:
            if not isinstance(alias, str) or not alias.strip():
                raise ValidationError(
                    f"Parameter '{parameter_name}' for '{plugin_name}' has invalid aliases.",
                )
            normalized_alias = _require_normalized_identifier(
                alias,
                f"Alias for parameter '{parameter_name}'",
            )
            existing_owner = alias_owner_by_key.get(normalized_alias)
            if existing_owner is not None and existing_owner != parameter_name:
                raise ValidationError(
                    f"Parameter alias '{alias}' for '{plugin_name}' collides with '{existing_owner}'.",
                )
            alias_owner_by_key[normalized_alias] = parameter_name


def validate_parameter_schema_document(
    plugin_name: str,
    schema: JSONDict,
    *,
    require_categories: bool = False,
) -> None:
    _require_normalized_identifier(plugin_name, "Plugin name")
    parameters_value = schema.get("parameters")
    if not is_json_dict(parameters_value):
        raise ValidationError(f"Schema for '{plugin_name}' has invalid parameters.")
    validate_parameter_definitions(parameters_value)
    _validate_parameter_identities(plugin_name, parameters_value)
    categories_value = schema.get("parameter_categories")
    if categories_value is None:
        if require_categories:
            raise ValidationError(
                f"Schema for '{plugin_name}' requires parameter categories.",
            )
        return
    if not is_json_dict(categories_value):
        raise ValidationError(f"Schema for '{plugin_name}' has invalid parameter categories.")


def declared_parameter_names(schema: JSONDict) -> frozenset[str]:
    parameters_value = schema.get("parameters")
    if not is_json_dict(parameters_value):
        return frozenset()
    return frozenset(name for name in parameters_value if isinstance(name, str) and name)
