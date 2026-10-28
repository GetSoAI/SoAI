"""SoAI - Actual legacy AUTO goals and protected native facility planning [backend/hardware/gpu_tuning/startup_legacy_planning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_operation_types import GPUControlPreflightRejection
from core.hardware.gpu_physical_identity import GPUInventoryReadState, GPUPhysicalDevice
from core.hardware.gpu_recovery_records import (
    GPUOriginalObservationState,
    GPURecoveryRecord,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS
from core.logging.protocols import TraceLogger
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.startup_recorded_facilities import acquire_recorded_startup_facilities
from hardware.gpu_tuning.startup_scope_accounting import same_startup_physical_device
from hardware.gpu_tuning.startup_scope_types import (
    GPULegacyResetDevicePlan,
    GPULegacyResetRoster,
    GPUStartupFacilityScope,
)
from hardware.gpu_tuning.vendor_backend_apply import prepare_vendor_backend_settings
from hardware.vendors.amd.sysfs_telemetry import read_radeon_control_facilities

__all__ = ("plan_gpu_legacy_reset_device",)

_FIELDS = GPU_DIRECT_SETTING_FIELDS


def plan_gpu_legacy_reset_device(
    target: GPUPhysicalDevice,
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
    operation_id: str,
    rosters: tuple[GPULegacyResetRoster, ...],
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> GPULegacyResetDevicePlan:
    facilities = list(
        acquire_recorded_startup_facilities(target, executor, logger, gpu_services, initial_records)
    )
    protected_fields = {facility.field for facility in facilities}
    routes = _available_routes(target, rosters)
    selected: dict[str, JSONDict] = {}
    radeon_facilities: dict[str, bool] | None = None
    if (
        target.vendor == "amd"
        and target.platform_driver == "radeon"
        and target.identity.pci_bdf_full is not None
    ):
        try:
            radeon_facilities = read_radeon_control_facilities(target.identity.pci_bdf_full)
        except (OSError, StateError, ValidationError):
            radeon_facilities = None
    for field in _FIELDS:
        if field in protected_fields:
            continue
        if target.platform_driver == "radeon":
            unsupported = radeon_facilities is not None and radeon_facilities[field] is False
            facilities.append(
                GPUStartupFacilityScope(
                    target,
                    "radeon",
                    field,
                    (),
                    (
                        GPUOriginalObservationState.UNSUPPORTED
                        if unsupported
                        else GPUOriginalObservationState.UNAVAILABLE
                    ),
                    (
                        "radeon_native_field_unsupported"
                        if unsupported
                        else "radeon_reset_authority_unavailable"
                    ),
                )
            )
            continue
        chosen: GPURecoveryRecord | None = None
        for backend in routes:
            if backend == "intel_i915" or (
                backend == "amd_adl" and field in ("power_limit", "fan_speed")
            ):
                continue
            candidate = prepare_vendor_backend_settings(
                executor=executor,
                logger=logger,
                nvidia_settings_controller=gpu_services.nvidia_settings_controller,
                gpu_services=gpu_services,
                target=target,
                operation_id=operation_id,
                normalized_settings={field: "auto"},
                requested_modes={field: "auto"},
                grouped_settings={backend: {field: "auto"}},
                clock_control_types=None,
            )
            if isinstance(candidate, GPURecoveryRecord):
                chosen = candidate
                if backend not in selected:
                    selected[backend] = {}
                selected[backend][field] = "auto"
                facilities.append(
                    GPUStartupFacilityScope(
                        target,
                        chosen.members[0].backend or backend,
                        field,
                        tuple(
                            recovery_member_key(member)
                            for member in chosen.members
                            if member.field == field
                        ),
                        GPUOriginalObservationState.OBSERVED,
                        None,
                    )
                )
                break
        if chosen is None:
            if routes == ("amd_adl",) and field in ("power_limit", "fan_speed"):
                facilities.append(
                    GPUStartupFacilityScope(
                        target,
                        "amd_adl",
                        field,
                        (),
                        GPUOriginalObservationState.UNSUPPORTED,
                        "adl_public_quantity_unsupported",
                    )
                )
                continue
            if routes == ("intel_i915",) and field != "core_clock":
                facilities.append(
                    GPUStartupFacilityScope(
                        target,
                        "intel_i915",
                        field,
                        (),
                        GPUOriginalObservationState.UNSUPPORTED,
                        "i915_frequency_only_route",
                    )
                )
                continue
            if _unsupported_platform_controls(target, gpu_services, initial_records):
                facilities.append(
                    GPUStartupFacilityScope(
                        target,
                        "platform",
                        field,
                        (),
                        GPUOriginalObservationState.UNSUPPORTED,
                        "platform_control_route_unsupported",
                    )
                )
                continue
            facilities.append(
                GPUStartupFacilityScope(
                    target,
                    routes[0] if routes else target.vendor,
                    field,
                    (),
                    GPUOriginalObservationState.UNAVAILABLE,
                    (
                        "i915_original_frequency_authority_unavailable"
                        if routes == ("intel_i915",) and field == "core_clock"
                        else "native_automatic_original_or_target_unavailable"
                    ),
                )
            )
    if not selected:
        if {facility.field for facility in facilities}.issuperset(_FIELDS) and all(
            facility.state
            in (GPUOriginalObservationState.OBSERVED, GPUOriginalObservationState.UNSUPPORTED)
            for facility in facilities
        ):
            return GPULegacyResetDevicePlan(target, tuple(facilities), None, None)
        return GPULegacyResetDevicePlan(
            target,
            tuple(facilities),
            None,
            GPUControlPreflightRejection(
                "native_query_failed",
                (
                    "i915 core clock recovery requires its recorded original minimum and maximum frequencies. Preserve the recovery evidence and repair the missing original authority before retrying control recovery."
                    if any(
                        facility.reason_code == "i915_original_frequency_authority_unavailable"
                        for facility in facilities
                    )
                    else "The uncovered native automatic goal is unavailable."
                ),
            ),
        )
    requested = {
        field: value for settings in selected.values() for field, value in settings.items()
    }
    captured = prepare_vendor_backend_settings(
        executor=executor,
        logger=logger,
        nvidia_settings_controller=gpu_services.nvidia_settings_controller,
        gpu_services=gpu_services,
        target=target,
        operation_id=operation_id,
        normalized_settings=requested,
        requested_modes={field: "auto" for field in requested},
        grouped_settings=selected,
        clock_control_types=None,
    )
    if isinstance(captured, GPUControlPreflightRejection):
        return GPULegacyResetDevicePlan(target, tuple(facilities), None, captured)
    if protected_fields.intersection(member.field for member in captured.members):
        return GPULegacyResetDevicePlan(
            target,
            tuple(facilities),
            None,
            GPUControlPreflightRejection(
                "native_query_failed", "Automatic setup overlaps recorded native authority."
            ),
        )
    for captured_backend, field in dict.fromkeys(
        (member.backend, member.field) for member in captured.members
    ):
        facility = GPUStartupFacilityScope(
            target,
            captured_backend or target.vendor,
            field,
            tuple(
                recovery_member_key(member)
                for member in captured.members
                if member.backend == captured_backend and member.field == field
            ),
            GPUOriginalObservationState.OBSERVED,
            None,
        )
        positions = [index for index, existing in enumerate(facilities) if existing.field == field]
        if positions:
            facilities[positions[0]] = facility
        else:
            facilities.append(facility)
    return GPULegacyResetDevicePlan(target, tuple(facilities), captured, None)


def _available_routes(
    target: GPUPhysicalDevice, rosters: tuple[GPULegacyResetRoster, ...]
) -> tuple[str, ...]:
    observed = {
        row.backend
        for row in rosters
        if row.vendor == target.vendor
        and row.state == GPUInventoryReadState.OBSERVED
        and any(same_startup_physical_device(target, peer) for peer in row.devices)
    }
    if target.vendor == "nvidia":
        return tuple(
            public
            for native, public in (
                ("nvapi", "nvidia_nvapi"),
                ("nvml", "nvidia_nvml"),
                ("nvidia_settings", "nvidia_settings"),
            )
            if native in observed
        )
    if target.vendor == "amd" and "amd_adl" in observed:
        return ("amd_adl",)
    if target.vendor == "amd" and "amd_smi" in observed:
        return ("amd_smi", "amd_overdrive")
    if target.vendor == "intel":
        return tuple(route for route in ("intel_xpum", "intel_i915") if route in observed)
    return ()


def _unsupported_platform_controls(
    target: GPUPhysicalDevice,
    services: GpuServiceDependencies,
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> bool:
    path = target.identity.native_device_path
    if (
        target.vendor == "intel"
        and services.nvidia_nvml_gate.runtime_platform.is_macos
        and path is not None
        and path.startswith("darwin:ioreg:IOService:/")
        and target.platform_driver == "IOPCIDevice"
    ):
        return not any(record.device_id == target.device_id for record in initial_records)
    if target.vendor != "unknown" or path is None or not path.startswith("linux:"):
        return False
    compatible_prefixes = {
        "vc4-drm": ("brcm,bcm2835-vc4", "brcm,bcm2711-vc5"),
        "kgsl-3d": ("qcom,kgsl-3d0",),
        "kgsl": ("qcom,kgsl-3d0",),
        "msm_drm": ("qcom,sde-kms",),
    }
    if target.platform_driver not in compatible_prefixes:
        return False
    return any(
        value in compatible_prefixes[target.platform_driver] for value in target.platform_compatible
    )
