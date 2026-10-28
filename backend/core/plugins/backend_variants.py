"""SoAI - Plugin backend variant public helpers [backend/core/plugins/backend_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.compute_driver_observations import read_compute_driver_observation
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
    observation = read_compute_driver_observation(compute_drivers, "cuda")
    if "cuda" not in gpu_features and not observation.family_present:
        return False, "No CUDA GPU feature or driver detected."
    cuda_version = observation.version
    if cuda_version is None and observation.reported_version is None:
        return False, "CUDA driver runtime version was not reported."
    if cuda_version is None or cuda_version.major < required_cuda_major:
        return (
            False,
            (
                f"Detected CUDA driver runtime {observation.reported_version}; "
                f"{torch_requirement_label} requires CUDA {required_cuda_major}.x."
            ),
        )
    return True, ""
