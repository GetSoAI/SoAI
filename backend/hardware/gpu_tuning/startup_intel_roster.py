"""SoAI - Actual Intel startup discovery and platform applicability [backend/hardware/gpu_tuning/startup_intel_roster.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_physical_identity import (
    GPUInventoryReadState,
    GPUPhysicalDevice,
    GPUPhysicalIdentity,
)
from hardware.gpu_inventory.executable_resolution import GpuExecutableState
from hardware.gpu_tuning.startup_scope_accounting import (
    startup_absent_native_vendors,
    startup_darwin_intel_route_inapplicable,
)
from hardware.gpu_tuning.startup_scope_types import GPULegacyResetRoster
from hardware.operations import create_device_id
from hardware.vendors.intel.i915_frequency import acquire_i915_frequency_roster
from hardware.vendors.intel.physical_binding import acquire_intel_discovery_observations

if TYPE_CHECKING:
    from core.hardware.gpu_physical_identity import GPUPhysicalSnapshot
    from core.hardware.gpu_recovery_records import (
        GPURecoveryRecord,
        GPUStartupLegacyRecoveryRecord,
        GPUStartupRecoveryRecord,
    )
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies


OPERATION_HARDWARE_GPU_TUNING_STARTUP_INTEL_ROSTER = "hardware.gpu_tuning.startup_intel_roster"
OPERATION_HARDWARE_GPU_TUNING_STARTUP_INTEL_ROSTER_I915 = (
    "hardware.gpu_tuning.startup_intel_roster.i915"
)


__all__ = (
    "acquire_startup_intel_roster",
    "acquire_startup_i915_roster",
)


def acquire_startup_intel_roster(
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    services: GpuServiceDependencies,
    acquisition_id: str,
    *,
    physical_snapshot: GPUPhysicalSnapshot,
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> GPULegacyResetRoster:
    if "intel" in startup_absent_native_vendors(physical_snapshot, initial_records, acquisition_id):
        return GPULegacyResetRoster(
            "intel",
            "intel_xpum",
            acquisition_id,
            GPUInventoryReadState.OBSERVED,
            (),
            "physical_vendor_absent",
        )
    platform = services.nvidia_nvml_gate.runtime_platform
    if (
        not platform.is_linux
        and not platform.is_windows
        and platform.is_macos
        and startup_darwin_intel_route_inapplicable(physical_snapshot, initial_records)
    ):
        return GPULegacyResetRoster(
            "intel",
            "intel_xpum",
            acquisition_id,
            GPUInventoryReadState.OBSERVED,
            (),
            "darwin_intel_route_inapplicable",
        )
    if not platform.is_linux and not platform.is_windows:
        return GPULegacyResetRoster(
            "intel",
            "intel_xpum",
            acquisition_id,
            GPUInventoryReadState.RUNTIME_UNAVAILABLE,
            (),
            "intel_control_platform_unavailable",
        )
    if (
        services.intel_executable.state != GpuExecutableState.FOUND
        or services.intel_executable.path is None
    ):
        return GPULegacyResetRoster(
            "intel",
            "intel_xpum",
            acquisition_id,
            GPUInventoryReadState.RUNTIME_UNAVAILABLE,
            (),
            "intel_executable_unavailable",
        )
    try:
        observed = acquire_intel_discovery_observations(
            executor, executable=services.intel_executable.path
        )
        if any(row.identity is None for row in observed.devices):
            raise StateError("Intel discovery has unresolved physical peers.")
        devices = tuple(
            GPUPhysicalDevice(
                create_device_id(
                    "gpu", row.identity.uuid or f"intel-pci-{row.identity.pci_bdf_full}"
                ),
                "intel",
                row.identity,
                None,
                None,
                row.pci_bdf_observations,
            )
            for row in observed.devices
            if row.identity is not None
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        details: JSONDict = {"acquisition_id": acquisition_id}
        if isinstance(exception, SoAIError) and exception.details is not None:
            details["native_details"] = dict(exception.details)
        log_exception(
            logger,
            exception,
            message="Intel startup native discovery failed.",
            operation=OPERATION_HARDWARE_GPU_TUNING_STARTUP_INTEL_ROSTER,
            details=details,
            level="warning",
        )
        return GPULegacyResetRoster(
            "intel",
            "intel_xpum",
            acquisition_id,
            (
                GPUInventoryReadState.INVALID_RESPONSE
                if isinstance(exception, ValidationError)
                else GPUInventoryReadState.QUERY_FAILED
            ),
            (),
            "native_roster_query_failed",
        )
    return GPULegacyResetRoster(
        "intel",
        "intel_xpum",
        acquisition_id,
        (
            GPUInventoryReadState.RUNTIME_UNAVAILABLE
            if observed.devices
            else GPUInventoryReadState.OBSERVED
        ),
        devices,
        "intel_healthy_control_scope_unproved" if observed.devices else None,
    )


def acquire_startup_i915_roster(
    logger: TraceLogger,
    services: GpuServiceDependencies,
    acquisition_id: str,
    *,
    physical_snapshot: GPUPhysicalSnapshot,
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> GPULegacyResetRoster:
    if "intel" in startup_absent_native_vendors(physical_snapshot, initial_records, acquisition_id):
        return GPULegacyResetRoster(
            "intel",
            "intel_i915",
            acquisition_id,
            GPUInventoryReadState.OBSERVED,
            (),
            "physical_vendor_absent",
        )
    platform = services.nvidia_nvml_gate.runtime_platform
    if (
        not platform.is_linux
        and not platform.is_windows
        and platform.is_macos
        and startup_darwin_intel_route_inapplicable(physical_snapshot, initial_records)
    ):
        return GPULegacyResetRoster(
            "intel",
            "intel_i915",
            acquisition_id,
            GPUInventoryReadState.OBSERVED,
            (),
            "darwin_intel_route_inapplicable",
        )
    if not services.nvidia_nvml_gate.runtime_platform.is_linux:
        return GPULegacyResetRoster(
            "intel",
            "intel_i915",
            acquisition_id,
            GPUInventoryReadState.RUNTIME_UNAVAILABLE,
            (),
            "i915_control_platform_unavailable",
        )
    try:
        states = acquire_i915_frequency_roster()
        devices = tuple(
            GPUPhysicalDevice(
                create_device_id("gpu", f"intel-pci-{state.pci_bdf}"),
                "intel",
                GPUPhysicalIdentity(None, state.pci_bdf),
                None,
                None,
                (state.pci_bdf,),
            )
            for state in states
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="i915 startup native discovery failed.",
            operation=OPERATION_HARDWARE_GPU_TUNING_STARTUP_INTEL_ROSTER_I915,
            details={"acquisition_id": acquisition_id},
            level="warning",
        )
        return GPULegacyResetRoster(
            "intel",
            "intel_i915",
            acquisition_id,
            (
                GPUInventoryReadState.INVALID_RESPONSE
                if isinstance(exception, ValidationError)
                else GPUInventoryReadState.QUERY_FAILED
            ),
            (),
            "i915_native_roster_query_failed",
        )
    return GPULegacyResetRoster(
        "intel",
        "intel_i915",
        acquisition_id,
        GPUInventoryReadState.OBSERVED,
        devices,
        None,
    )
