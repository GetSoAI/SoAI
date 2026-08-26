"""SoAI - Backend variant option manifest validation [backend/core/plugins/backend_variant_option_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.config.gpu_binding import normalize_gpu_binding_runtime_family
from core.errors.exceptions import ValidationError
from core.plugins.backend_variant_availability import (
    backend_variant_availability_type_is_valid,
)
from core.plugins.backend_variant_ids import (
    AUTO_BACKEND_VARIANT_ID,
    require_backend_variant_id,
)
from core.plugins.backend_variant_platforms import (
    normalize_backend_variant_supported_arch,
    normalize_backend_variant_supported_os,
    normalize_backend_variant_supported_platforms,
)
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("require_backend_variant_options",)


def require_backend_variant_options(value: JSONValue, *, field_name: str) -> list[JSONDict]:
    if value is None:
        return []
    if not isinstance(value, list | tuple):
        raise ValidationError(f"{field_name} must be a list of backend variant option objects.")
    normalized_options: list[JSONDict] = []
    seen_ids: set[str] = set()
    for index, option in enumerate(value):
        if not isinstance(option, Mapping):
            raise ValidationError(f"{field_name}[{index}] must be a JSON object.")
        normalized_options.append(
            _require_backend_variant_option(option, index, field_name, seen_ids),
        )
    return normalized_options


def _require_backend_variant_option(
    option: Mapping[str, JSONValue],
    index: int,
    field_name: str,
    seen_ids: set[str],
) -> JSONDict:
    variant_id = require_backend_variant_id(option.get("id"))
    if variant_id == AUTO_BACKEND_VARIANT_ID:
        raise ValidationError(f"{field_name}[{index}] must not declare the automatic variant.")
    if variant_id in seen_ids:
        raise ValidationError(f"{field_name} contains duplicate variant '{variant_id}'.")
    seen_ids.add(variant_id)
    _validate_option_metadata(option, index, field_name)
    normalized: JSONDict = {
        "id": variant_id,
        "label": coerce_optional_trimmed_str(option.get("label")) or variant_id,
        "available": _require_available(option, index, field_name),
    }
    _copy_optional_fields(normalized, option)
    return normalized


def _validate_option_metadata(option: Mapping[str, JSONValue], index: int, field_name: str) -> None:
    availability_type = coerce_optional_trimmed_str(option.get("availability_type"))
    if availability_type is not None and not backend_variant_availability_type_is_valid(
        availability_type,
    ):
        raise ValidationError(f"{field_name}[{index}].availability_type is unsupported.")
    if option.get("supported_os") is not None and not normalize_backend_variant_supported_os(
        option.get("supported_os"),
    ):
        raise ValidationError(f"{field_name}[{index}].supported_os must contain supported OS IDs.")
    if option.get("supported_arch") is not None and not normalize_backend_variant_supported_arch(
        option.get("supported_arch"),
    ):
        raise ValidationError(
            f"{field_name}[{index}].supported_arch must contain supported CPU architecture IDs.",
        )
    if option.get(
        "supported_platforms",
    ) is not None and not normalize_backend_variant_supported_platforms(
        option.get("supported_platforms"),
    ):
        raise ValidationError(
            f"{field_name}[{index}].supported_platforms must contain supported platform IDs.",
        )
    runtime_family = option.get("gpu_binding_runtime_family")
    if runtime_family is not None and normalize_gpu_binding_runtime_family(runtime_family) is None:
        raise ValidationError(f"{field_name}[{index}].gpu_binding_runtime_family is unsupported.")


def _require_available(option: Mapping[str, JSONValue], index: int, field_name: str) -> bool:
    available_value = option.get("available")
    if available_value is None:
        return True
    if isinstance(available_value, bool):
        return available_value
    raise ValidationError(f"{field_name}[{index}].available must be a boolean.")


def _copy_optional_fields(normalized: JSONDict, option: Mapping[str, JSONValue]) -> None:
    for key in ("description", "unavailable_reason", "platform_label", "availability_type"):
        value = coerce_optional_trimmed_str(option.get(key))
        if value is not None:
            normalized[key] = value.lower() if key == "availability_type" else value
    runtime_family = normalize_gpu_binding_runtime_family(
        option.get("gpu_binding_runtime_family"),
    )
    if runtime_family is not None:
        normalized["gpu_binding_runtime_family"] = runtime_family
    supported_os = normalize_backend_variant_supported_os(option.get("supported_os"))
    supported_arch = normalize_backend_variant_supported_arch(option.get("supported_arch"))
    supported_platforms = normalize_backend_variant_supported_platforms(
        option.get("supported_platforms"),
    )
    if supported_os:
        normalized["supported_os"] = supported_os
    if supported_arch:
        normalized["supported_arch"] = supported_arch
    if supported_platforms:
        normalized["supported_platforms"] = supported_platforms
