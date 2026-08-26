"""SoAI - Individual validators for system capability requirements [backend/plugins/state/capability_validators.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.state.capability_normalization import format_capability_values
from plugins.state.capability_results import (
    CapabilityValidationResult,
    create_capability_failure,
    create_capability_success,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CapabilityValidationResult",
    "to_detail_dict",
    "validate_drivers_capability",
    "validate_gpu_capability",
    "validate_gpu_features_capability",
)

LOGGER_NAME = "SoAI.plugins.state.capability_validators"


def validate_gpu_capability(
    normalized_requirement: list[str] | None,
    raw_requirement: list[str],
    host_snapshot: JSONDict,
) -> CapabilityValidationResult | None:
    if normalized_requirement is None:
        return None
    gpu_info_value = host_snapshot.get("gpu")
    gpu_info = gpu_info_value if isinstance(gpu_info_value, dict) else {}
    vendors_value = gpu_info.get("vendors")
    vendors = vendors_value if isinstance(vendors_value, list) else []
    detected = [
        str(vendor_entry).strip().lower() for vendor_entry in vendors if str(vendor_entry).strip()
    ]
    if not coerce_bool_with_recovery(
        gpu_info.get("inventory_available"),
        logger=get_logger(LOGGER_NAME),
        operation="plugins.state.capability_validators.coerce_bool_flag",
        default=False,
    ):
        message = (
            "Requires GPU support. Hardware inventory is unavailable, so compatibility "
            "cannot be verified."
        )
        return create_capability_failure(
            "gpu",
            "unknown",
            raw_requirement,
            detected,
            message,
        )
    if not coerce_bool_with_recovery(
        gpu_info.get("available"),
        logger=get_logger(LOGGER_NAME),
        operation="plugins.state.capability_validators.coerce_bool_flag",
        default=False,
    ):
        required_text = format_capability_values(raw_requirement)
        return create_capability_failure(
            "gpu",
            "missing",
            raw_requirement,
            [],
            f"Requires GPU support ({required_text}). No compatible GPU detected.",
        )
    normalized_allowed = set(normalized_requirement)
    if "any" not in normalized_allowed and (
        not any(vendor in normalized_allowed for vendor in detected)
    ):
        required_text = format_capability_values(raw_requirement)
        detected_text = format_capability_values(detected)
        return create_capability_failure(
            "gpu",
            "vendor_mismatch",
            raw_requirement,
            detected,
            f"Requires GPU support ({required_text}). Detected vendors: {detected_text}.",
        )
    return create_capability_success("gpu")


def validate_gpu_features_capability(
    normalized_requirement: list[str] | None,
    raw_requirement: list[str],
    host_snapshot: JSONDict,
) -> CapabilityValidationResult | None:
    if normalized_requirement is None or not normalized_requirement:
        return None
    if "any" in normalized_requirement:
        return create_capability_success("gpu_features")
    gpu_info_value = host_snapshot.get("gpu")
    gpu_info = gpu_info_value if isinstance(gpu_info_value, dict) else {}
    detected_features: list[str] = []
    features_value = gpu_info.get("features")
    if isinstance(features_value, list):
        for entry in features_value:
            feature = str(entry).strip().lower()
            if feature and feature not in detected_features:
                detected_features.append(feature)
    missing = [feature for feature in normalized_requirement if feature not in detected_features]
    if missing:
        status = "missing" if len(missing) == len(normalized_requirement) else "partial"
        required_text = format_capability_values(raw_requirement)
        detected_text = format_capability_values(detected_features) if detected_features else "NONE"
        return create_capability_failure(
            "gpu_features",
            status,
            raw_requirement,
            detected_features,
            f"Requires GPU features ({required_text}). Detected: {detected_text}.",
        )
    return create_capability_success("gpu_features")


def validate_drivers_capability(
    normalized_requirement: list[str] | None,
    raw_requirement: list[str],
    host_snapshot: JSONDict,
) -> CapabilityValidationResult | None:
    if normalized_requirement is None:
        return None
    normalized_value = host_snapshot.get("normalized_drivers")
    normalized_available = normalized_value if isinstance(normalized_value, list) else []
    detected_value = host_snapshot.get("drivers")
    detected_driver_names = detected_value if isinstance(detected_value, list) else []
    require_any = "any" in normalized_requirement
    missing_specific = [
        driver_name
        for driver_name in normalized_requirement
        if driver_name != "any" and driver_name not in normalized_available
    ]
    if (require_any and not normalized_available) or missing_specific:
        required_text = format_capability_values(raw_requirement)
        detected_text = (
            format_capability_values(detected_driver_names) if detected_driver_names else "NONE"
        )
        message_end = (
            "None detected."
            if require_any and (not normalized_available)
            else f"Detected: {detected_text}."
        )
        return create_capability_failure(
            "drivers",
            "missing",
            raw_requirement,
            detected_driver_names,
            f"Requires drivers ({required_text}). {message_end}",
        )
    return create_capability_success("drivers")


def to_detail_dict(result: CapabilityValidationResult) -> JSONDict:
    required_value: JSONValue = (
        result.required
        if isinstance(result.required, str | int | float | bool | list | dict)
        or result.required is None
        else str(result.required)
    )
    detected_value: JSONValue = (
        result.detected
        if isinstance(result.detected, str | int | float | bool | list | dict)
        or result.detected is None
        else str(result.detected)
    )
    return {
        "capability": result.capability,
        "status": result.status,
        "required": required_value,
        "detected": detected_value,
    }
