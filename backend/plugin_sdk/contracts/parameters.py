"""SoAI - Plugin SDK parameter schema and clonable field definitions [backend/plugin_sdk/contracts/parameters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypedDict, TypeGuard, override

from core.errors.exceptions import StateError
from core.openai.upstream_request_customization import (
    build_openai_request_customization_schema_additions,
)
from core.types.json_value import copy_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

    type ClonableFieldType = Literal["port", "path", "string"]
    type ParameterDefault = JSONValue | type[NoDefault]

__all__ = (
    "ClonableField",
    "NoDefault",
    "ParameterDefinition",
    "build_parameter_schema",
)


class ClonableField(TypedDict):
    name: str
    display_name: str
    field_type: ClonableFieldType
    required: bool


class NoDefault:
    __slots__ = ()

    @override
    def __repr__(self) -> str:
        return "NoDefault"

    def __bool__(self) -> bool:
        return False


def _is_json_default(value: ParameterDefault) -> TypeGuard[JSONValue]:
    return value is not NoDefault


@dataclass(slots=True)
class ParameterDefinition:
    name: str
    group: str
    default: ParameterDefault = field(default_factory=lambda: NoDefault)
    cli_name: str | None = None
    aliases: tuple[str, ...] = ()
    description: str | None = None
    semantic_role: str | None = None
    extra: Mapping[str, JSONValue] = field(default_factory=dict)

    @property
    def has_default(self) -> bool:
        return self.default is not NoDefault

    def to_mapping(self) -> JSONDict:
        payload: JSONDict = {
            "group": self.group,
            "aliases": list(self.aliases),
            "has_default": self.has_default,
        }
        if self.has_default:
            default_value = self.default
            if not _is_json_default(default_value):
                raise StateError("ParameterDefinition.default is NoDefault unexpectedly.")
            payload["default"] = default_value
        if self.cli_name:
            payload["cli_name"] = self.cli_name
        if self.description:
            payload["description"] = self.description
        if self.semantic_role:
            payload["semantic_role"] = self.semantic_role
        if self.extra:
            for key, value in self.extra.items():
                if key not in payload:
                    payload[key] = value
        return payload


def build_parameter_schema(
    *params: ParameterDefinition,
    parameter_categories: JSONDict | None = None,
    openai_request_field_customization: bool = False,
) -> JSONDict:
    parameters: JSONDict = {param.name: param.to_mapping() for param in params}
    schema: JSONDict = {"parameters": parameters}
    categories = copy_json_dict(parameter_categories) if parameter_categories else {}
    if openai_request_field_customization:
        additions, category_additions = build_openai_request_customization_schema_additions()
        collisions = set(parameters) & set(additions)
        if collisions:
            raise StateError(
                "OpenAI request customization parameter names must not be defined manually: "
                f"{', '.join(sorted(collisions))}.",
            )
        parameters.update(additions)
        for category_name, category_definition in category_additions.items():
            if category_name not in categories:
                categories[category_name] = category_definition
    if categories:
        schema["parameter_categories"] = categories
    return schema
