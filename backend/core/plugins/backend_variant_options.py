"""SoAI - Backend variant option normalization [backend/core/plugins/backend_variant_options.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.gpu_binding import normalize_gpu_binding_runtime_family
from core.plugins.backend_variant_availability import (
    BACKEND_VARIANT_AVAILABILITY_AVAILABLE,
    BACKEND_VARIANT_AVAILABILITY_HARDWARE_WARNING,
    BACKEND_VARIANT_AVAILABILITY_UNAVAILABLE,
    normalize_backend_variant_availability_type,
)
from core.plugins.backend_variant_ids import (
    AUTO_BACKEND_VARIANT_ID,
    normalize_backend_variant_id,
)
from core.plugins.backend_variant_platforms import (
    format_backend_variant_platform_label,
    normalize_backend_variant_supported_arch,
    normalize_backend_variant_supported_os,
    normalize_backend_variant_supported_platforms,
    supported_platforms_to_os,
)
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_auto_backend_variant_option",
    "normalize_backend_variant_options",
)


def build_auto_backend_variant_option() -> JSONDict:
    return {
        "id": AUTO_BACKEND_VARIANT_ID,
        "label": "Auto",
        "description": "Use SoAI's automatic backend selection.",
        "available": True,
        "selectable": True,
        "availability_type": BACKEND_VARIANT_AVAILABILITY_AVAILABLE,
    }


def normalize_backend_variant_options(options: list[JSONDict]) -> list[JSONDict]:
    normalized_options: list[JSONDict] = [build_auto_backend_variant_option()]
    seen_ids: set[str] = {AUTO_BACKEND_VARIANT_ID}
    for option in options:
        normalized = _normalize_variant_option(option)
        if normalized is None:
            continue
        variant_id = str(normalized["id"])
        if variant_id in seen_ids:
            continue
        seen_ids.add(variant_id)
        normalized_options.append(normalized)
    return normalized_options


def _normalize_variant_option(option: JSONDict) -> JSONDict | None:
    variant_id = normalize_backend_variant_id(option.get("id"))
    if variant_id is None:
        return None
    option_platforms = _normalize_option_platforms(option)
    platform_label = _resolve_platform_label(option, option_platforms)
    availability_type = normalize_backend_variant_availability_type(
        option,
        option_platforms.supported_os,
        option_platforms.supported_arch,
        option_platforms.supported_platforms,
    )
    selectable = availability_type != BACKEND_VARIANT_AVAILABILITY_UNAVAILABLE
    normalized: JSONDict = {
        "id": variant_id,
        "label": _append_platform_label(
            coerce_optional_trimmed_str(option.get("label")) or variant_id,
            platform_label,
        ),
        "available": selectable,
        "selectable": selectable,
        "availability_type": availability_type,
    }
    _copy_optional_option_fields(normalized, option, option_platforms, platform_label)
    reason = _resolve_unavailable_reason(
        availability_type,
        coerce_optional_trimmed_str(option.get("unavailable_reason")),
        platform_label,
    )
    if reason is not None:
        normalized["unavailable_reason"] = reason
    return normalized


@dataclass(frozen=True, slots=True)
class _OptionPlatforms:
    supported_os: list[str]
    supported_arch: list[str]
    supported_platforms: list[str]


def _normalize_option_platforms(option: Mapping[str, JSONValue]) -> _OptionPlatforms:
    return _OptionPlatforms(
        normalize_backend_variant_supported_os(option.get("supported_os")),
        normalize_backend_variant_supported_arch(option.get("supported_arch")),
        normalize_backend_variant_supported_platforms(option.get("supported_platforms")),
    )


def _resolve_platform_label(
    option: Mapping[str, JSONValue],
    platforms: _OptionPlatforms,
) -> str | None:
    platform_label = coerce_optional_trimmed_str(option.get("platform_label"))
    label_os = platforms.supported_os or supported_platforms_to_os(platforms.supported_platforms)
    if platform_label is None and label_os:
        return format_backend_variant_platform_label(label_os)
    return platform_label


def _append_platform_label(label: str, platform_label: str | None) -> str:
    if platform_label is None:
        return label
    suffix = f" - {platform_label}"
    return label if label.endswith(suffix) else f"{label}{suffix}"


def _copy_optional_option_fields(
    normalized: JSONDict,
    option: JSONDict,
    platforms: _OptionPlatforms,
    platform_label: str | None,
) -> None:
    description = coerce_optional_trimmed_str(option.get("description"))
    if description is not None:
        normalized["description"] = description
    if platform_label is not None:
        normalized["platform_label"] = platform_label
    if platforms.supported_os:
        normalized["supported_os"] = list(platforms.supported_os)
    if platforms.supported_arch:
        normalized["supported_arch"] = list(platforms.supported_arch)
    if platforms.supported_platforms:
        normalized["supported_platforms"] = list(platforms.supported_platforms)
    runtime_family = normalize_gpu_binding_runtime_family(
        option.get("gpu_binding_runtime_family"),
    )
    if runtime_family is not None:
        normalized["gpu_binding_runtime_family"] = runtime_family


def _resolve_unavailable_reason(
    availability_type: str,
    unavailable_reason: str | None,
    platform_label: str | None,
) -> str | None:
    if unavailable_reason is not None:
        return unavailable_reason
    if availability_type == BACKEND_VARIANT_AVAILABILITY_HARDWARE_WARNING:
        if platform_label is not None:
            return f"Requires compatible hardware on {platform_label}; selection is allowed."
        return "Requires compatible hardware; selection is allowed."
    if availability_type != BACKEND_VARIANT_AVAILABILITY_UNAVAILABLE:
        return None
    if platform_label is not None:
        return f"Available on {platform_label}."
    return "This backend variant is unavailable on this system."
