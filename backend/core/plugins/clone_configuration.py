"""SoAI - Clone configuration contract validation [backend/core/plugins/clone_configuration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, TypeGuard

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from typing import Literal

    from core.plugins.protocols_instance import ClonableFieldProtocol

    type CloneFieldType = Literal["path", "port", "string"]

__all__ = ("validate_clone_configuration_inputs",)

_FIELD_TYPES = frozenset({"path", "port", "string"})


def _is_clone_field_type(value: JSONValue) -> TypeGuard[CloneFieldType]:
    return isinstance(value, str) and value in _FIELD_TYPES


def _validate_override(field_name: str, field_type: str, value: JSONValue) -> None:
    if field_type == "port":
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
            raise ValidationError(f"Clone override '{field_name}' must be a port from 1 to 65535.")
        return
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Clone override '{field_name}' must be a non-empty string.")


def validate_clone_configuration_inputs(
    clonable_fields: Sequence[ClonableFieldProtocol],
    field_overrides: Mapping[str, JSONValue] | None,
) -> tuple[JSONDict, ...]:
    validated_fields: list[JSONDict] = []
    field_types: dict[str, CloneFieldType] = {}
    for index, field in enumerate(clonable_fields):
        name = field.get("name")
        display_name = field.get("display_name")
        field_type = field.get("field_type")
        required = field.get("required")
        valid_name = isinstance(name, str) and bool(name.strip())
        valid_display_name = isinstance(display_name, str) and bool(display_name.strip())
        valid_contract = _is_clone_field_type(field_type) and isinstance(required, bool)
        if not valid_name or not valid_display_name or not valid_contract:
            raise ValidationError(f"Clone field metadata at index {index} is malformed.")
        normalized_name = name.strip()
        if normalized_name in field_types:
            raise ValidationError(f"Clone field metadata duplicates '{normalized_name}'.")
        normalized_type = field_type
        field_types[normalized_name] = normalized_type
        validated_fields.append(
            {
                "name": normalized_name,
                "display_name": display_name.strip(),
                "field_type": normalized_type,
                "required": required,
            }
        )
    for field_name, value in (field_overrides or {}).items():
        override_field_type = field_types.get(field_name)
        if override_field_type is None:
            raise ValidationError(
                f"Clone override '{field_name}' is not declared by the source plugin."
            )
        _validate_override(field_name, override_field_type, value)
    return tuple(validated_fields)
