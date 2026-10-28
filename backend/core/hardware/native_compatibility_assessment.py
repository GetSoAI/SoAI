"""SoAI - Evidence-based native runtime compatibility assessment [backend/core/hardware/native_compatibility_assessment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.gpu_binding import gpu_binding_selected_device_ids
from core.errors.exceptions import ValidationError
from core.hardware.compute_driver_observations import read_compute_driver_observation
from core.hardware.gpu_architecture import read_observed_nvidia_architecture_code
from core.hardware.native_compatibility import require_cpu_instruction_features
from core.hardware.native_execution_devices import (
    resolve_native_execution_devices,
    resolve_native_runtime_default_device,
)
from core.meta.versioning import parse_semantic_version
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, JSONValue
from core.validation.integers import is_strict_int

__all__ = (
    "NativeCompatibilityAssessment",
    "assess_native_compatibility",
    "require_native_compatibility",
    "has_native_runtime_evidence",
)

if TYPE_CHECKING:
    from typing import Literal

    type CompatibilityStatus = Literal["compatible", "incompatible", "unknown"]


@dataclass(frozen=True, slots=True)
class NativeCompatibilityAssessment:
    status: CompatibilityStatus
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> JSONDict:
        return {"status": self.status, "reasons": list(self.reasons)}


def has_native_runtime_evidence(capabilities: Mapping[str, JSONValue], runtime: str) -> bool:
    families = ("rocm", "hip") if runtime == "rocm" else (runtime,)
    features = capabilities.get("gpu_features")
    if isinstance(features, list) and any(
        isinstance(feature, str) and feature.strip().casefold() in families for feature in features
    ):
        return True
    drivers = capabilities.get("compute_drivers")
    return isinstance(drivers, dict) and any(
        read_compute_driver_observation(drivers, family).version is not None for family in families
    )


def require_native_compatibility(assessment: NativeCompatibilityAssessment) -> None:
    if assessment.status != "incompatible":
        return
    error = ValidationError(
        "The selected runtime requires CPU instructions that are unavailable. Select another compatible runtime."
        if "cpu_features_unsupported" in assessment.reasons
        else "The selected runtime requires hardware or driver capabilities that are unavailable. Select another available runtime or compatible hardware."
    )
    error.code = "backend_runtime_incompatible"
    error.public_message = error.message
    error.public_details = assessment.to_dict()
    raise error


def assess_native_compatibility(
    requirements: Mapping[str, JSONValue],
    capabilities: Mapping[str, JSONValue],
    *,
    gpu_binding: JSONValue,
    gpu_inventory: Mapping[str, JSONValue] | None,
    runtime_device: Mapping[str, JSONValue] | None = None,
) -> NativeCompatibilityAssessment:
    outcomes: list[NativeCompatibilityAssessment] = []
    if requirements.keys() - {"complete", "driver", "cpu_features", "device_architecture"}:
        outcomes.append(NativeCompatibilityAssessment("unknown", ("requirements_incomplete",)))
    driver = requirements.get("driver")
    if driver is not None:
        outcomes.append(_assess_driver(driver, capabilities))
    features = requirements.get("cpu_features")
    if features is not None:
        outcomes.append(_assess_cpu(features, capabilities))
    architecture = requirements.get("device_architecture")
    if architecture is not None:
        outcomes.append(
            _assess_architecture(
                architecture,
                gpu_binding,
                gpu_inventory,
                runtime_device,
                capabilities.get("platform_id"),
            )
        )
    if requirements.get("complete") is not True:
        outcomes.append(NativeCompatibilityAssessment("unknown", ("requirements_incomplete",)))
    status: CompatibilityStatus = "compatible"
    if any(outcome.status == "incompatible" for outcome in outcomes):
        status = "incompatible"
    elif any(outcome.status == "unknown" for outcome in outcomes):
        status = "unknown"
    return NativeCompatibilityAssessment(
        status, tuple(dict.fromkeys(reason for outcome in outcomes for reason in outcome.reasons))
    )


def _assess_driver(
    requirement: JSONValue, capabilities: Mapping[str, JSONValue]
) -> NativeCompatibilityAssessment:
    if (
        not isinstance(requirement, dict)
        or requirement.keys() - {"family", "minimum", "maximum"}
        or not isinstance(family := requirement.get("family"), str)
        or not family.strip()
    ):
        return NativeCompatibilityAssessment("unknown", ("requirements_incomplete",))
    drivers = capabilities.get("compute_drivers")
    observed_version = (
        read_compute_driver_observation(drivers, family).version
        if isinstance(drivers, dict)
        else None
    )
    if observed_version is None:
        return NativeCompatibilityAssessment("unknown", ("driver_observation_unavailable",))
    minimum, maximum = requirement.get("minimum"), requirement.get("maximum")
    if (minimum is not None and not isinstance(minimum, str)) or (
        maximum is not None and not isinstance(maximum, str)
    ):
        return NativeCompatibilityAssessment("unknown", ("requirements_incomplete",))
    try:
        lower_bound = parse_semantic_version(minimum) if isinstance(minimum, str) else None
        upper_bound = parse_semantic_version(maximum) if isinstance(maximum, str) else None
    except ValidationError:
        return NativeCompatibilityAssessment("unknown", ("requirements_incomplete",))
    if lower_bound is not None and upper_bound is not None and lower_bound > upper_bound:
        return NativeCompatibilityAssessment("unknown", ("requirements_incomplete",))
    if (lower_bound is not None and observed_version < lower_bound) or (
        upper_bound is not None and observed_version > upper_bound
    ):
        return NativeCompatibilityAssessment("incompatible", ("driver_runtime_unsupported",))
    return NativeCompatibilityAssessment("compatible")


def _assess_cpu(
    requirement: JSONValue, capabilities: Mapping[str, JSONValue]
) -> NativeCompatibilityAssessment:
    if isinstance(requirement, dict):
        platform_id = capabilities.get("platform_id")
        if not isinstance(platform_id, str):
            return NativeCompatibilityAssessment("unknown", ("cpu_observation_unavailable",))
        requirement = requirement.get(platform_id)
    if not isinstance(requirement, list) or not all(
        isinstance(item, str) and item.strip() for item in requirement
    ):
        return NativeCompatibilityAssessment("unknown", ("requirements_incomplete",))
    if not requirement:
        return NativeCompatibilityAssessment("compatible")
    features = capabilities.get("cpu_features")
    if capabilities.get("cpu_features_observation") != "complete" or not isinstance(features, list):
        return NativeCompatibilityAssessment("unknown", ("cpu_observation_unavailable",))
    if not all(isinstance(feature, str) for feature in features):
        return NativeCompatibilityAssessment("unknown", ("cpu_observation_unavailable",))
    try:
        require_cpu_instruction_features(
            capabilities, [feature.lower() for feature in requirement if isinstance(feature, str)]
        )
    except ValidationError:
        return NativeCompatibilityAssessment("incompatible", ("cpu_features_unsupported",))
    return NativeCompatibilityAssessment("compatible")


def _assess_architecture(
    requirement: JSONValue,
    gpu_binding: JSONValue,
    inventory: Mapping[str, JSONValue] | None,
    runtime_device: Mapping[str, JSONValue] | None,
    platform_id: JSONValue,
) -> NativeCompatibilityAssessment:
    if (
        not isinstance(requirement, dict)
        or requirement.keys() - {"vendor", "supported", "unsupported", "execution_scope"}
        or requirement.get("vendor") != "nvidia"
        or requirement.get("execution_scope", "all_bound") not in ("all_bound", "runtime_default")
    ):
        return NativeCompatibilityAssessment("unknown", ("requirements_incomplete",))
    supported, unsupported = requirement.get("supported"), requirement.get("unsupported")
    if isinstance(supported, dict):
        supported = supported.get(platform_id) if isinstance(platform_id, str) else None
    if (
        not isinstance(supported, list)
        or not isinstance(unsupported, list)
        or not all(is_strict_int(code) and code >= 0 for code in (*supported, *unsupported))
        or set(supported).intersection(unsupported)
    ):
        return NativeCompatibilityAssessment("unknown", ("requirements_incomplete",))
    if inventory is None:
        return NativeCompatibilityAssessment("unknown", ("gpu_observation_unavailable",))
    metadata = inventory.get("component_status")
    observation = metadata.get("gpu") if isinstance(metadata, dict) else None
    if (
        not isinstance(observation, dict)
        or observation.get("status") != "available"
        or not _architecture_observation_valid(observation)
    ):
        return NativeCompatibilityAssessment("unknown", ("gpu_observation_unavailable",))
    try:
        selected_ids = gpu_binding_selected_device_ids(gpu_binding)
    except ValidationError:
        return NativeCompatibilityAssessment("unknown", ("gpu_identity_unavailable",))
    devices = resolve_native_execution_devices(inventory, gpu_binding)
    if not devices:
        return NativeCompatibilityAssessment("unknown", ("gpu_identity_unavailable",))
    if requirement.get("execution_scope", "all_bound") == "runtime_default":
        default_devices = resolve_native_runtime_default_device(
            devices, explicitly_selected=bool(selected_ids), runtime_device=runtime_device
        )
        if default_devices is None:
            return NativeCompatibilityAssessment("unknown", ("gpu_identity_unavailable",))
        devices = default_devices
    codes = [read_observed_nvidia_architecture_code(entry) for entry in devices]
    if any(code in unsupported for code in codes if code is not None):
        return NativeCompatibilityAssessment("incompatible", ("device_architecture_unsupported",))
    if any(entry.get("type") != "nvidia" for entry in devices):
        return NativeCompatibilityAssessment("incompatible", ("device_vendor_unsupported",))
    if any(code is None or code not in supported for code in codes):
        return NativeCompatibilityAssessment("unknown", ("gpu_architecture_unavailable",))
    return NativeCompatibilityAssessment("compatible")


def _architecture_observation_valid(observation: JSONDict) -> bool:
    if observation.get("sampled_current") is True:
        return True
    if observation.get("sampled_current") is not False:
        return False
    observed = observation.get("observed_at_ms")
    checked = observation.get("checked_at_ms")
    expires = observation.get("valid_until_ms")
    revision = observation.get("inventory_revision")
    return (
        is_strict_int(observed)
        and is_strict_int(checked)
        and is_strict_int(expires)
        and is_strict_int(revision)
        and revision >= 0
        and min(observed, checked) >= 0
        and max(observed, checked) <= epoch_ms() < expires
    )
