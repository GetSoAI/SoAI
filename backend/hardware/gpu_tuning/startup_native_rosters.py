"""SoAI - Fresh native GPU fleet acquisition and diagnostic ownership [backend/hardware/gpu_tuning/startup_native_rosters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_physical_identity import (
    GPUInventoryReadState,
    GPUPhysicalSnapshot,
)
from core.hardware.gpu_recovery_records import (
    GPURecoveryRecord,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from hardware.gpu_tuning.startup_intel_roster import (
    acquire_startup_i915_roster,
    acquire_startup_intel_roster,
)
from hardware.gpu_tuning.startup_native_roster_observations import (
    absent_native_roster,
    failed_native_roster,
    native_roster_device,
    unavailable_nvidia_roster,
)
from hardware.gpu_tuning.startup_scope_accounting import (
    startup_absent_native_vendors,
)
from hardware.gpu_tuning.startup_scope_types import GPULegacyResetRoster
from hardware.vendors.amd.adl_physical_inventory import acquire_adl_physical_devices
from hardware.vendors.amd.physical_binding import acquire_amd_physical_roster
from hardware.vendors.nvidia.command_physical_binding import acquire_nvidia_command_roster
from hardware.vendors.nvidia.internal_protocols import NvmlIdentityModuleProtocol
from hardware.vendors.nvidia.nvapi_function_acquisition import resolve_nvapi_function
from hardware.vendors.nvidia.nvapi_physical_binding import acquire_nvapi_physical_roster
from hardware.vendors.nvidia.nvml_physical_binding import acquire_nvml_physical_roster
from hardware.vendors.nvidia.settings_control_queries import NvidiaSettingsSession
from hardware.vendors.nvidia.settings_physical_binding import acquire_settings_physical_roster
from hardware.vendors.nvidia.smi_display_environment import (
    DisplaySearchStatus,
    detect_display_environment,
)
from hardware.vendors.nvidia.tuning_nvml import pynvml_module_ref

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies


__all__ = ("acquire_startup_native_rosters",)


def acquire_startup_native_rosters(
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    services: GpuServiceDependencies,
    acquisition_id: str,
    *,
    physical_snapshot: GPUPhysicalSnapshot,
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> tuple[GPULegacyResetRoster, ...]:
    rosters: list[GPULegacyResetRoster] = []
    absent = startup_absent_native_vendors(physical_snapshot, initial_records, acquisition_id)
    if "nvidia" in absent:
        rosters.append(absent_native_roster("nvidia", "nvidia_smi", acquisition_id))
    else:
        try:
            command = acquire_nvidia_command_roster(
                executor, executable=services.nvidia_smi_executable
            )
            devices = tuple(
                native_roster_device("nvidia", row.identity, row.pci_bdf_observations)
                for row in command.devices
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            rosters.append(
                failed_native_roster("nvidia", "nvidia_smi", acquisition_id, logger, exception)
            )
        else:
            rosters.append(
                GPULegacyResetRoster(
                    "nvidia",
                    "nvidia_smi",
                    acquisition_id,
                    GPUInventoryReadState.OBSERVED,
                    devices,
                    None,
                )
            )
    if "nvidia" in absent:
        rosters.append(absent_native_roster("nvidia", "nvml", acquisition_id))
    else:
        module = pynvml_module_ref
        if module is None or not services.nvidia_nvml_gate.nvml_available:
            rosters.append(
                GPULegacyResetRoster(
                    "nvidia",
                    "nvml",
                    acquisition_id,
                    GPUInventoryReadState.RUNTIME_UNAVAILABLE,
                    (),
                    "nvml_runtime_unavailable",
                )
            )
        else:
            native_failures: tuple[type[Exception], ...] = (
                module.NVMLError,
                *HANDLED_RUNTIME_EXCEPTIONS,
            )
            try:
                if not isinstance(module, NvmlIdentityModuleProtocol):
                    raise StateError("NVML identity module facilities are incomplete.")
                with services.nvidia_nvml_gate.session():
                    observed = acquire_nvml_physical_roster(module)
                    devices = tuple(
                        native_roster_device("nvidia", row.identity, row.pci_bdf_observations)
                        for row in observed
                    )
            except native_failures as exception:
                rosters.append(
                    failed_native_roster("nvidia", "nvml", acquisition_id, logger, exception)
                )
            else:
                rosters.append(
                    GPULegacyResetRoster(
                        "nvidia",
                        "nvml",
                        acquisition_id,
                        GPUInventoryReadState.OBSERVED,
                        devices,
                        None,
                    )
                )
    if services.nvidia_nvml_gate.runtime_platform.is_windows:
        if "amd" in absent:
            rosters.append(absent_native_roster("amd", "amd_adl", acquisition_id))
        else:
            try:
                runtime = services.adl_runtime
                if runtime is None:
                    raise StateError("The app ADL native resource owner is unavailable.")
                with runtime.session() as session:
                    devices = tuple(
                        row.device for row in acquire_adl_physical_devices(session, executor)
                    )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                rosters.append(
                    failed_native_roster("amd", "amd_adl", acquisition_id, logger, exception)
                )
            else:
                rosters.append(
                    GPULegacyResetRoster(
                        "amd",
                        "amd_adl",
                        acquisition_id,
                        GPUInventoryReadState.OBSERVED,
                        devices,
                        None,
                    )
                )
    else:
        amd_devices = tuple(
            device for device in physical_snapshot.devices if device.vendor == "amd"
        )
        radeon_only = (
            bool(amd_devices)
            and all(device.platform_driver == "radeon" for device in amd_devices)
            and any(
                vendor.vendor == "amd" and vendor.state == GPUInventoryReadState.OBSERVED
                for vendor in physical_snapshot.vendors
            )
        )
        if "amd" in absent:
            rosters.append(absent_native_roster("amd", "amd_smi", acquisition_id))
        elif radeon_only:
            rosters.append(
                GPULegacyResetRoster(
                    "amd",
                    "radeon",
                    acquisition_id,
                    GPUInventoryReadState.OBSERVED,
                    amd_devices,
                    None,
                )
            )
        else:
            try:
                amd = acquire_amd_physical_roster(executor)
                devices = tuple(
                    native_roster_device("amd", row.identity, row.pci_bdf_observations)
                    for row in amd
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                rosters.append(
                    failed_native_roster("amd", "amd_smi", acquisition_id, logger, exception)
                )
            else:
                rosters.append(
                    GPULegacyResetRoster(
                        "amd",
                        "amd_smi",
                        acquisition_id,
                        GPUInventoryReadState.OBSERVED,
                        devices,
                        None,
                    )
                )
    rosters.append(
        acquire_startup_intel_roster(
            executor,
            logger,
            services,
            acquisition_id,
            physical_snapshot=physical_snapshot,
            initial_records=initial_records,
        )
    )
    rosters.append(
        acquire_startup_i915_roster(
            logger,
            services,
            acquisition_id,
            physical_snapshot=physical_snapshot,
            initial_records=initial_records,
        )
    )
    if services.nvidia_nvml_gate.runtime_platform.is_windows:
        query = services.nvidia_nvml_gate.nvapi_support.native_query_interface
        if "nvidia" in absent:
            rosters.append(absent_native_roster("nvidia", "nvapi", acquisition_id))
        elif query is None:
            rosters.append(
                unavailable_nvidia_roster("nvapi", acquisition_id, "nvapi_runtime_unavailable")
            )
        else:
            try:
                enumerate_gpus = resolve_nvapi_function(
                    "NvAPI_EnumPhysicalGPUs", query_interface=query
                )
                read_bus = resolve_nvapi_function("NvAPI_GPU_GetBusId", query_interface=query)
                if enumerate_gpus is None or read_bus is None:
                    raise StateError("NvAPI actual native fleet facilities are unavailable.")
                native = acquire_nvapi_physical_roster(
                    executor,
                    executable=services.nvidia_smi_executable,
                    enumerate_gpus=enumerate_gpus,
                    read_bus=read_bus,
                )
                devices = tuple(row.device for row in native)
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                rosters.append(
                    failed_native_roster("nvidia", "nvapi", acquisition_id, logger, exception)
                )
            else:
                rosters.append(
                    GPULegacyResetRoster(
                        "nvidia",
                        "nvapi",
                        acquisition_id,
                        GPUInventoryReadState.OBSERVED,
                        devices,
                        None,
                    )
                )
    if services.nvidia_nvml_gate.runtime_platform.is_linux:
        controller = services.nvidia_settings_controller
        if "nvidia" in absent:
            rosters.append(absent_native_roster("nvidia", "nvidia_settings", acquisition_id))
        elif controller is None:
            rosters.append(
                unavailable_nvidia_roster(
                    "nvidia_settings", acquisition_id, "settings_runtime_unavailable"
                )
            )
        else:
            try:
                display = detect_display_environment(logger, query=controller.native_query)
                if display.status != DisplaySearchStatus.USABLE or display.display is None:
                    raise StateError("NVIDIA settings actual fleet display is unavailable.")
                observed_settings = acquire_settings_physical_roster(
                    NvidiaSettingsSession(
                        controller.native_query, display.display, display.xauthority
                    )
                )
                devices = tuple(
                    native_roster_device("nvidia", row.identity, row.pci_bdf_observations)
                    for row in observed_settings
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                rosters.append(
                    failed_native_roster(
                        "nvidia", "nvidia_settings", acquisition_id, logger, exception
                    )
                )
            else:
                rosters.append(
                    GPULegacyResetRoster(
                        "nvidia",
                        "nvidia_settings",
                        acquisition_id,
                        GPUInventoryReadState.OBSERVED,
                        devices,
                        None,
                    )
                )
    return tuple(rosters)
