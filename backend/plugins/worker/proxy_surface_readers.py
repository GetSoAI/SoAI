"""SoAI - Proxy plugin surface value readers [backend/plugins/worker/proxy_surface_readers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ValidationError
from core.openai.compatibility import (
    ExternalProviderMode,
    normalize_external_provider_mode,
)
from core.plugins.protocols_instance import ClonableFieldProtocol
from core.types.json import JSONValue
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_json_object
from plugins.manifest.class_field_contract import (
    PLUGIN_FIELD_CLONABLE_FIELDS,
    PLUGIN_FIELD_EXTERNAL_PROVIDER_MODE,
)
from plugins.worker.surface import PluginRuntimeSurface

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "read_bool_surface_field",
    "read_clonable_surface_fields",
    "read_int_surface_field",
    "read_json_dict_list_surface_field",
    "read_mapping_surface_field",
    "read_optional_str_surface_field",
    "read_provider_mode_surface_field",
    "read_str_surface_field",
    "read_string_tuple_surface_field",
)


def read_str_surface_field(surface: PluginRuntimeSurface, name: str) -> str:
    value = surface.field(name)
    if not isinstance(value, str):
        raise ValidationError(f"Plugin worker surface field '{name}' must be a string.")
    return value


def read_optional_str_surface_field(
    surface: PluginRuntimeSurface,
    name: str,
) -> str | None:
    value = surface.field(name)
    return value if isinstance(value, str) and value else None


def read_int_surface_field(surface: PluginRuntimeSurface, name: str) -> int | None:
    value = surface.field(name)
    if value is None:
        return None
    if not is_strict_int(value):
        raise ValidationError(f"Plugin worker surface field '{name}' must be an integer.")
    return value


def read_bool_surface_field(surface: PluginRuntimeSurface, name: str) -> bool:
    value = surface.field(name)
    if not isinstance(value, bool):
        raise ValidationError(f"Plugin worker surface field '{name}' must be a boolean.")
    return value


def read_mapping_surface_field(
    surface: PluginRuntimeSurface,
    name: str,
) -> Mapping[str, JSONValue]:
    return require_json_object(
        surface.field(name),
        label=f"Plugin worker surface field '{name}'",
        build_error=ValidationError,
        invalid_message=f"Plugin worker surface field '{name}' must be a JSON object.",
    )


def read_json_dict_list_surface_field(
    surface: PluginRuntimeSurface,
    name: str,
) -> tuple[JSONDict, ...]:
    value = surface.field(name)
    if not isinstance(value, list | tuple):
        raise ValidationError(f"Plugin worker surface field '{name}' must be a JSON object list.")
    items: list[JSONDict] = []
    for index, item in enumerate(value):
        items.append(
            require_json_object(
                item,
                label=f"Plugin worker surface field '{name}[{index}]'",
                build_error=ValidationError,
                invalid_message=(
                    f"Plugin worker surface field '{name}[{index}]' must be a JSON object."
                ),
            ),
        )
    return tuple(items)


def read_string_tuple_surface_field(
    surface: PluginRuntimeSurface,
    name: str,
) -> tuple[str, ...]:
    value = surface.field(name)
    if not isinstance(value, list | tuple):
        raise ValidationError(f"Plugin worker surface field '{name}' must be a string list.")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(
                f"Plugin worker surface field '{name}' must contain only strings.",
            )
        items.append(item)
    return tuple(items)


def read_clonable_surface_fields(
    surface: PluginRuntimeSurface,
) -> tuple[ClonableFieldProtocol, ...]:
    value = surface.field(PLUGIN_FIELD_CLONABLE_FIELDS)
    if not isinstance(value, list | tuple):
        raise ValidationError("Plugin worker surface field 'CLONABLE_FIELDS' must be a list.")
    fields: list[ClonableFieldProtocol] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValidationError(
                f"Plugin worker surface field 'CLONABLE_FIELDS[{index}]' must be a JSON object.",
            )
        name = item.get("name")
        display_name = item.get("display_name")
        field_type = _field_type(item.get("field_type"))
        required = item.get("required")
        if (
            isinstance(name, str)
            and isinstance(display_name, str)
            and field_type is not None
            and isinstance(required, bool)
        ):
            fields.append(
                {
                    "name": name,
                    "display_name": display_name,
                    "field_type": field_type,
                    "required": required,
                },
            )
            continue
        raise ValidationError(
            f"Plugin worker surface field 'CLONABLE_FIELDS[{index}]' is malformed.",
        )
    return tuple(fields)


def _field_type(value: JSONValue | None) -> Literal["port", "path", "string"] | None:
    if value == "port":
        return "port"
    if value == "path":
        return "path"
    if value == "string":
        return "string"
    return None


def read_provider_mode_surface_field(
    surface: PluginRuntimeSurface,
) -> ExternalProviderMode:
    value = surface.field(PLUGIN_FIELD_EXTERNAL_PROVIDER_MODE)
    if isinstance(value, Enum | str):
        mode = normalize_external_provider_mode(value)
        raw = value.value if isinstance(value, Enum) else value
        if mode is ExternalProviderMode.NONE and str(raw).strip().lower() not in {
            ExternalProviderMode.NONE.value,
            ExternalProviderMode.NONE.name.lower(),
        }:
            raise ValidationError(
                "Plugin worker surface field 'EXTERNAL_PROVIDER_MODE' is invalid.",
            )
        return mode
    raise ValidationError("Plugin worker surface field 'EXTERNAL_PROVIDER_MODE' must be a string.")
