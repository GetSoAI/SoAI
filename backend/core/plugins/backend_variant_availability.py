"""SoAI - Backend variant availability metadata [backend/core/plugins/backend_variant_availability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.plugins.backend_variant_platforms import (
    current_backend_variant_arch,
    current_backend_variant_os,
    current_backend_variant_platform,
)
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "BACKEND_VARIANT_AVAILABILITY_AVAILABLE",
    "BACKEND_VARIANT_AVAILABILITY_HARDWARE_WARNING",
    "BACKEND_VARIANT_AVAILABILITY_UNAVAILABLE",
    "backend_variant_availability_type_is_valid",
    "normalize_backend_variant_availability_type",
)

BACKEND_VARIANT_AVAILABILITY_AVAILABLE = "available"
BACKEND_VARIANT_AVAILABILITY_HARDWARE_WARNING = "hardware_warning"
BACKEND_VARIANT_AVAILABILITY_UNAVAILABLE = "unavailable"
_AVAILABILITY_TYPES = frozenset(
    {
        BACKEND_VARIANT_AVAILABILITY_AVAILABLE,
        BACKEND_VARIANT_AVAILABILITY_HARDWARE_WARNING,
        BACKEND_VARIANT_AVAILABILITY_UNAVAILABLE,
    },
)


def normalize_backend_variant_availability_type(
    option: JSONDict,
    supported_os: list[str],
    supported_arch: list[str],
    supported_platforms: list[str],
) -> str:
    availability_value = coerce_optional_trimmed_str(option.get("availability_type"))
    availability_type = (
        availability_value.lower()
        if availability_value is not None and availability_value.lower() in _AVAILABILITY_TYPES
        else None
    )
    if supported_os and current_backend_variant_os() not in supported_os:
        return BACKEND_VARIANT_AVAILABILITY_UNAVAILABLE
    if supported_arch and current_backend_variant_arch() not in supported_arch:
        return BACKEND_VARIANT_AVAILABILITY_UNAVAILABLE
    if supported_platforms and current_backend_variant_platform() not in supported_platforms:
        return BACKEND_VARIANT_AVAILABILITY_UNAVAILABLE
    if availability_type is not None:
        return availability_type
    if option.get("available") is False:
        return BACKEND_VARIANT_AVAILABILITY_UNAVAILABLE
    return BACKEND_VARIANT_AVAILABILITY_AVAILABLE


def backend_variant_availability_type_is_valid(value: str) -> bool:
    return value.lower() in _AVAILABILITY_TYPES
