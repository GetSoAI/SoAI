"""SoAI - Plugin backend variant public helpers [backend/core/plugins/backend_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.plugins.backend_variant_ids import (
    AUTO_BACKEND_VARIANT_ID,
    normalize_backend_variant_id,
    require_backend_variant_id,
)
from core.plugins.backend_variant_option_validation import (
    require_backend_variant_options,
)
from core.plugins.backend_variant_options import (
    build_auto_backend_variant_option,
    normalize_backend_variant_options,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "AUTO_BACKEND_VARIANT_ID",
    "build_auto_backend_variant_option",
    "count_available_backend_variant_options",
    "has_explicit_backend_variant_option",
    "is_backend_variant_available",
    "normalize_backend_variant_id",
    "normalize_backend_variant_options",
    "require_backend_variant_id",
    "require_backend_variant_options",
    "require_known_backend_variant_id",
    "resolve_cuda_backend_availability",
)


def count_available_backend_variant_options(options: list[JSONDict]) -> int:
    available_non_auto_count = 0
    for option in options:
        variant_id = normalize_backend_variant_id(option.get("id"))
        if variant_id is None or variant_id == AUTO_BACKEND_VARIANT_ID:
            continue
        if option.get("selectable") is False or option.get("available") is False:
            continue
        available_non_auto_count += 1
    return available_non_auto_count if available_non_auto_count > 0 else 1


def has_explicit_backend_variant_option(options: list[JSONDict]) -> bool:
    for option in options:
        variant_id = normalize_backend_variant_id(option.get("id"))
        if variant_id is not None and variant_id != AUTO_BACKEND_VARIANT_ID:
            return True
    return False


def require_known_backend_variant_id(variant_id: JSONValue, options: list[JSONDict]) -> str:
    normalized_variant_id = require_backend_variant_id(variant_id)
    for option in options:
        option_id = normalize_backend_variant_id(option.get("id"))
        if option_id != normalized_variant_id:
            continue
        if option.get("selectable") is False or option.get("available") is False:
            raise ValidationError(f"Backend variant '{normalized_variant_id}' is unavailable.")
        return normalized_variant_id
    raise ValidationError(f"Backend variant '{normalized_variant_id}' is not supported.")


def is_backend_variant_available(variant_id: JSONValue, options: list[JSONDict]) -> bool:
    normalized_variant_id = normalize_backend_variant_id(variant_id)
    if normalized_variant_id is None:
        return False
    for option in options:
        if normalize_backend_variant_id(option.get("id")) == normalized_variant_id:
            return option.get("selectable") is not False and option.get("available") is not False
    return False


def resolve_cuda_backend_availability(
    system_capabilities: JSONValue,
    *,
    required_cuda_major: int,
    torch_requirement_label: str,
) -> tuple[bool, str]:
    if not isinstance(system_capabilities, Mapping):
        return False, "CUDA capability probe failed."
    gpu_features_value = system_capabilities.get("gpu_features")
    gpu_features = (
        {str(feature).lower() for feature in gpu_features_value}
        if isinstance(gpu_features_value, list | tuple)
        else set[str]()
    )
    compute_drivers_value = system_capabilities.get("compute_drivers")
    compute_drivers: dict[str, JSONValue] = {}
    if isinstance(compute_drivers_value, Mapping):
        for driver_name, driver_payload in compute_drivers_value.items():
            if isinstance(driver_name, str):
                compute_drivers[driver_name] = driver_payload
    driver_names = {str(driver_name).lower() for driver_name in compute_drivers}
    if "cuda" not in gpu_features and "cuda" not in driver_names:
        return False, "No CUDA GPU feature or driver detected."
    cuda_version = _cuda_driver_runtime_version(compute_drivers)
    if cuda_version is None:
        return False, "CUDA driver runtime version was not reported."
    if not _cuda_driver_satisfies_required_major(cuda_version, required_cuda_major):
        return (
            False,
            (
                f"Detected CUDA driver runtime {cuda_version}; "
                f"{torch_requirement_label} requires CUDA {required_cuda_major}.x."
            ),
        )
    return True, ""


def _cuda_driver_runtime_version(compute_drivers: Mapping[str, JSONValue]) -> str | None:
    for driver_name, driver_payload in compute_drivers.items():
        if driver_name.lower() != "cuda" or not isinstance(driver_payload, Mapping):
            continue
        version_value = driver_payload.get("version")
        if isinstance(version_value, str) and version_value.strip():
            return version_value.strip()
    return None


def _cuda_driver_satisfies_required_major(version: str, required_cuda_major: int) -> bool:
    major_value = version.split(".", 1)[0].strip()
    try:
        major = int(major_value)
    except ValueError:
        return False
    return major >= required_cuda_major
