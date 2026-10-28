"""SoAI - ADL per-field clock quantities and native range validation [backend/hardware/vendors/amd/adl_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_identity_normalization import (
    observed_pci_bdf_conflicts,
)
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
)
from core.types.json import JSONDict
from core.validation.strict_integer import is_strict_int
from hardware.gpu_capabilities.payloads import (
    build_default_gpu_capabilities,
    mark_all_control_capabilities_unsupported,
    normalize_gpu_control_capabilities,
)
from hardware.gpu_inventory.physical_binding import resolve_gpu_physical_binding
from hardware.vendors.amd.adl_abi import AdlControlObservation
from hardware.vendors.amd.adl_physical_inventory import acquire_adl_physical_devices

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from hardware.vendors.amd.adl_session import AdlRuntime, AdlSession


OPERATION_HARDWARE_AMD_ADL_CAPABILITIES = "hardware.amd.adl.capabilities"


__all__ = (
    "AdlClockFeature",
    "ADL_CLOCK_FEATURES",
    "read_adl_clock_feature",
    "require_adl_clock_observation",
    "project_adl_clock_ranges",
    "bind_adl_controls",
    "sync_get_adl_capabilities",
)


@dataclass(frozen=True, slots=True)
class AdlClockFeature:
    field: str
    capability_key: str
    index: int
    capability_bit: int


ADL_CLOCK_FEATURES = (
    ("core_clock", "core_clock_mhz", 0, 1),
    ("mem_clock", "mem_clock_mhz", 8, 4),
)


def read_adl_clock_feature(field: str) -> AdlClockFeature:
    for feature_fields in ADL_CLOCK_FEATURES:
        feature = AdlClockFeature(*feature_fields)
        if field == feature.field:
            return feature
    raise ValidationError("ADL public controls support only proved clock quantities.")


def require_adl_clock_observation(
    observation: AdlControlObservation, field: str
) -> AdlClockFeature:
    feature = read_adl_clock_feature(field)
    if feature.index >= len(observation.features) or feature.index >= len(observation.current):
        raise StateError("ADL selected clock feature is absent from its actual native arrays.")
    bounds = observation.features[feature.index]
    if (
        bounds.feature_bit != feature.capability_bit
        or not observation.capabilities & feature.capability_bit
    ):
        raise StateError("ADL selected clock capability is unavailable.")
    values = (bounds.minimum, bounds.maximum, bounds.default, observation.current[feature.index])
    if any(not is_strict_int(value) or not 0 < value < 2**31 for value in values):
        raise ValidationError("ADL clock values are outside their native signed-integer ABI.")
    if not bounds.minimum <= bounds.default <= bounds.maximum:
        raise ValidationError("ADL native clock default conflicts with its actual range.")
    if not bounds.minimum <= observation.current[feature.index] <= bounds.maximum:
        raise ValidationError("ADL observed configured clock is outside its actual range.")
    return feature


def project_adl_clock_ranges(observation: AdlControlObservation) -> JSONDict:
    ranges: JSONDict = {}
    for feature_fields in ADL_CLOCK_FEATURES:
        feature = AdlClockFeature(*feature_fields)
        try:
            require_adl_clock_observation(observation, feature.field)
        except StateError:
            ranges[feature.capability_key] = {"supported": False, "reason": "unsupported"}
        except ValidationError:
            ranges[feature.capability_key] = {"supported": False, "reason": "probe_failed"}
        else:
            native = observation.features[feature.index]
            ranges[feature.capability_key] = {
                "min": native.minimum,
                "max": native.maximum,
                "default": native.default,
                "current": observation.current[feature.index],
                "unit": "MHz",
            }
    return ranges


def bind_adl_controls(
    session: AdlSession, executor: CommandExecutorProtocol, target: GPUPhysicalDevice
) -> AdlControlObservation:
    if target.vendor != "amd" or target.identity.windows_pnp_instance_id is None:
        raise ValidationError("ADL control requires its independent actual Windows PNP authority.")
    selected: JSONDict = {
        "device_id": target.device_id,
        "type": target.vendor,
        "uuid": target.identity.uuid,
        "pci_bdf_full": target.identity.pci_bdf_full,
        "windows_pnp_instance_id": target.identity.windows_pnp_instance_id,
        "pci_bdf_observations": list(target.pci_bdf_observations),
    }
    roster = acquire_adl_physical_devices(session, executor)
    candidates: list[JSONDict] = [
        {
            "device_id": row.device.device_id,
            "type": "amd",
            "windows_pnp_instance_id": row.device.identity.windows_pnp_instance_id,
            "pci_bdf_observations": list(row.device.pci_bdf_observations),
            "vendor_id": row.device.vendor_index,
        }
        for row in roster
    ]
    binding = resolve_gpu_physical_binding(selected, candidates)
    if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
        raise StateError("ADL selected actual physical adapter relation is unavailable.")
    physical = tuple(
        row
        for row in roster
        if row.device.identity.windows_pnp_instance_id == target.identity.windows_pnp_instance_id
    )
    if len(physical) != 1:
        raise ValidationError("ADL selected physical fleet relation is ambiguous.")
    observations = tuple(session.read_controls(adapter) for adapter in physical[0].adapters)
    canonical = observations[0]
    if any(
        (row.capabilities, row.features, row.current)
        != (canonical.capabilities, canonical.features, canonical.current)
        for row in observations
    ):
        raise StateError("ADL physical aliases report conflicting native control state.")
    if any(
        observed_pci_bdf_conflicts(actual, recorded)
        for actual in physical[0].device.pci_bdf_observations
        for recorded in target.pci_bdf_observations
    ):
        raise ValidationError(
            "ADL native adapter locator contradicts frozen physical observations."
        )
    if roster != acquire_adl_physical_devices(session, executor):
        raise StateError("ADL physical fleet changed during configured control observation.")
    return canonical


def sync_get_adl_capabilities(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    selected: JSONDict | None,
    runtime: AdlRuntime | None,
) -> JSONDict:
    payload = build_default_gpu_capabilities("AMD GPU")
    payload["control_backends"] = []
    if selected is None or runtime is None:
        return mark_all_control_capabilities_unsupported(payload, "tool_missing", force=True)
    try:
        binding = resolve_gpu_physical_binding(selected, [selected])
        if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
            raise ValidationError("ADL capability selection has no unique physical authority.")
        with runtime.session() as session:
            observation = bind_adl_controls(session, executor, binding.device)
            ranges = project_adl_clock_ranges(observation)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        if logger is not None:
            log_handled_exception(
                logger,
                exception,
                message="ADL optional clock capabilities are unavailable.",
                operation=OPERATION_HARDWARE_AMD_ADL_CAPABILITIES,
                level="trace",
            )
        return mark_all_control_capabilities_unsupported(payload, "probe_failed", force=True)
    payload["windows_pnp_instance_id"] = binding.device.identity.windows_pnp_instance_id
    payload["pci_bdf_observations"] = list(binding.device.pci_bdf_observations)
    payload["control_binding_state"] = GPUPhysicalBindingState.BOUND.value
    payload["control_binding_reason"] = None
    for feature_fields in ADL_CLOCK_FEATURES:
        feature = AdlClockFeature(*feature_fields)
        section = ranges[feature.capability_key]
        if not isinstance(section, dict):
            raise ValidationError("ADL clock projection lost its typed native quantity.")
        if "min" in section:
            section.update(
                {
                    "supported": True,
                    "requires_admin": True,
                    "control_backend": "amd_adl",
                    "auto_requires_apply": True,
                    "unsupported_reason": None,
                }
            )
            payload["control_backends"] = ["amd_adl"]
        else:
            section["unsupported_reason"] = section.pop("reason")
        payload[feature.capability_key] = section
    return normalize_gpu_control_capabilities(payload, None, enforce_backend=False)
