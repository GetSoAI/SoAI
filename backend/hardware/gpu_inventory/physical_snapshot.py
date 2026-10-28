"""SoAI - Fresh GPU physical scope acquisition [backend/hardware/gpu_inventory/physical_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import (
    GPUInventoryReadState,
    GPUPhysicalDevice,
    GPUPhysicalIdentity,
    GPUPhysicalSnapshot,
    GPUVendorObservation,
)
from core.hardware.gpu_physical_observations import (
    read_gpu_physical_identity,
    read_gpu_platform_observations,
    read_gpu_vendor,
)
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_inventory.darwin_inventory import read_darwin_gpu_inventory
from hardware.gpu_inventory.linux_physical_acquisition import (
    GPU_CLASS_IDS,
    read_linux_physical_acquisition,
)
from hardware.gpu_inventory.linux_platform import read_linux_platform_gpu_inventory
from hardware.gpu_inventory.pci_function_relationships import read_pci_function_relationship
from hardware.gpu_inventory.windows_adapters import (
    build_windows_gpu_entry,
    coerce_windows_gpu_name,
    detect_windows_adapter_vendor,
)
from hardware.gpu_inventory.windows_physical_acquisition import read_windows_physical_acquisition
from hardware.operations import create_device_id
from hardware.vendors.vendor_types import AMD_VENDOR, INTEL_VENDOR, NVIDIA_VENDOR, UNKNOWN_VENDOR

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimePlatformViewProtocol
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("acquire_gpu_physical_snapshot",)

_SCOPE_VENDORS = (NVIDIA_VENDOR, AMD_VENDOR, INTEL_VENDOR, UNKNOWN_VENDOR)


def acquire_gpu_physical_snapshot(
    executor: CommandExecutorProtocol,
    *,
    runtime_platform: RuntimePlatformViewProtocol,
    acquisition_id: str,
) -> GPUPhysicalSnapshot:
    require_canonical_trimmed_json_text(
        acquisition_id, error_message="GPU physical acquisition identifier is invalid."
    )
    if runtime_platform.is_linux and runtime_platform.is_windows:
        raise ValidationError("GPU physical acquisition platform is contradictory.")
    if runtime_platform.is_windows:
        return _windows_snapshot(executor, acquisition_id)
    if runtime_platform.is_macos:
        darwin = read_darwin_gpu_inventory(executor)
        return GPUPhysicalSnapshot(
            acquisition_id,
            tuple(
                _platform_device(row)
                for row in darwin.gpus
                if row.get("native_device_path") is not None
            ),
            tuple(
                GPUVendorObservation(vendor, darwin.state, darwin.reason_code)
                for vendor in _SCOPE_VENDORS
            ),
        )
    if not runtime_platform.is_linux:
        return GPUPhysicalSnapshot(
            acquisition_id,
            (),
            tuple(
                GPUVendorObservation(
                    vendor,
                    GPUInventoryReadState.RUNTIME_UNAVAILABLE,
                    "physical_platform_scope_unavailable",
                )
                for vendor in _SCOPE_VENDORS
            ),
        )
    acquisition = read_linux_physical_acquisition(executor)
    platform = read_linux_platform_gpu_inventory(sysfs_root="/sys")
    states = {vendor: acquisition.state for vendor in _SCOPE_VENDORS}
    reasons = {vendor: acquisition.reason_code for vendor in _SCOPE_VENDORS}
    devices = [
        GPUPhysicalDevice(
            device_id=create_device_id("gpu", f"{record.vendor}-pci-{record.pci_bdf}"),
            vendor=record.vendor,
            identity=GPUPhysicalIdentity(uuid=None, pci_bdf_full=record.slot),
            gpu_index=None,
            vendor_index=None,
            pci_bdf_observations=(record.slot, record.pci_bdf),
        )
        for record in sorted(acquisition.records, key=lambda row: row.slot)
        if record.pci_class_id in GPU_CLASS_IDS
        and read_pci_function_relationship(
            record, list(acquisition.records), platform.pci_drm_slots
        ).state
        != "secondary"
    ]
    devices.extend(_platform_device(row) for row in [*platform.gpus, *platform.display_adapters])
    for device in devices:
        if sum(peer.device_id == device.device_id for peer in devices) > 1:
            states[device.vendor] = GPUInventoryReadState.INVALID_RESPONSE
            reasons[device.vendor] = "ambiguous_physical_device_id"
    if (
        acquisition.state == GPUInventoryReadState.OBSERVED
        and states[UNKNOWN_VENDOR] == GPUInventoryReadState.OBSERVED
    ):
        states[UNKNOWN_VENDOR] = platform.state
        reasons[UNKNOWN_VENDOR] = platform.reason_code
    return GPUPhysicalSnapshot(
        acquisition_id,
        tuple(devices),
        tuple(
            GPUVendorObservation(vendor, states[vendor], reasons[vendor])
            for vendor in _SCOPE_VENDORS
        ),
    )


def _platform_device(row: JSONDict) -> GPUPhysicalDevice:
    identity = read_gpu_physical_identity(row)
    vendor = read_gpu_vendor(row)
    device_id = row.get("device_id")
    if identity is None or vendor is None or not isinstance(device_id, str):
        raise ValidationError("Actual platform GPU discovery has no physical identity.")
    driver, compatible = read_gpu_platform_observations(row)
    return GPUPhysicalDevice(device_id, vendor, identity, None, None, (), driver, compatible)


def _windows_snapshot(
    executor: CommandExecutorProtocol, acquisition_id: str
) -> GPUPhysicalSnapshot:
    acquisition = read_windows_physical_acquisition(executor)
    states = {vendor: acquisition.state for vendor in _SCOPE_VENDORS}
    reasons = {vendor: acquisition.reason_code for vendor in _SCOPE_VENDORS}
    if acquisition.state == GPUInventoryReadState.OBSERVED and not acquisition.records:
        states = {vendor: GPUInventoryReadState.RUNTIME_UNAVAILABLE for vendor in _SCOPE_VENDORS}
        reasons = {vendor: "wmi_physical_scope_unproven" for vendor in _SCOPE_VENDORS}
    devices: list[GPUPhysicalDevice] = []
    for index, row in enumerate(acquisition.records):
        name = coerce_windows_gpu_name(row.get("Name"))
        vendor = detect_windows_adapter_vendor(row, name)
        entry = build_windows_gpu_entry(
            gpu_info=row, gpu_index=index, vendor=vendor, vendor_id=None, name=name
        )
        identity = read_gpu_physical_identity(entry)
        if identity is None or identity.windows_pnp_instance_id is None:
            for affected in _SCOPE_VENDORS:
                if states[affected] == GPUInventoryReadState.OBSERVED:
                    states[affected] = GPUInventoryReadState.RUNTIME_UNAVAILABLE
                    reasons[affected] = "wmi_physical_scope_unproven"
            continue
        device_id = entry["device_id"]
        if not isinstance(device_id, str):
            raise ValidationError("Windows physical row lost its observed device identifier.")
        devices.append(GPUPhysicalDevice(device_id, vendor, identity, index, None, ()))
    for device in devices:
        if (
            sum(
                peer.identity.windows_pnp_instance_id == device.identity.windows_pnp_instance_id
                for peer in devices
            )
            > 1
        ):
            states[device.vendor] = GPUInventoryReadState.INVALID_RESPONSE
            reasons[device.vendor] = "ambiguous_physical_instance_id"
    return GPUPhysicalSnapshot(
        acquisition_id,
        tuple(devices),
        tuple(
            GPUVendorObservation(vendor, states[vendor], reasons[vendor])
            for vendor in _SCOPE_VENDORS
        ),
    )
