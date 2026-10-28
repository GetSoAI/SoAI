"""SoAI - Fresh NvAPI physical bus projection [backend/hardware/vendors/nvidia/nvapi_physical_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_identity_normalization import observed_pci_bdf_components
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState, GPUPhysicalDevice
from core.hardware.gpu_physical_observations import read_gpu_physical_identity
from core.validation.strict_integer import is_strict_int
from hardware.gpu_inventory.physical_binding import (
    match_gpu_physical_identity,
    resolve_gpu_physical_binding,
)
from hardware.operations import create_device_id
from hardware.vendors.nvidia.command_physical_binding import acquire_nvidia_command_roster

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.gpu_inventory.executable_resolution import GpuExecutableResolution
    from hardware.vendors.nvidia.command_physical_binding import (
        NvidiaCommandDevice,
    )
    from hardware.vendors.nvidia.internal_protocols import (
        NvApiBusFunctionProtocol,
        NvApiEnumPhysicalGpusFunctionProtocol,
    )


__all__ = (
    "NvApiBoundDevice",
    "acquire_nvapi_physical_binding",
    "acquire_nvapi_physical_roster",
)


@dataclass(frozen=True, slots=True)
class NvApiBoundDevice:
    device: GPUPhysicalDevice
    handle: ctypes.c_void_p
    bus_id: int
    slot_id: int | None
    slot_status: int | None


def acquire_nvapi_physical_binding(
    executor: CommandExecutorProtocol,
    *,
    target: GPUPhysicalDevice,
    executable: GpuExecutableResolution,
    enumerate_gpus: NvApiEnumPhysicalGpusFunctionProtocol,
    read_bus: NvApiBusFunctionProtocol,
    read_slot: NvApiBusFunctionProtocol | None,
) -> NvApiBoundDevice:
    if target.vendor.casefold() != "nvidia":
        raise ValidationError("NvAPI binding requires a NVIDIA physical target.")
    physical_roster = acquire_nvidia_command_roster(executor, executable=executable)
    target_entry: JSONDict = {
        "device_id": target.device_id,
        "type": target.vendor,
        "uuid": target.identity.uuid,
        "pci_bdf_full": target.identity.pci_bdf_full,
        "pci_bdf_observations": list(target.pci_bdf_observations),
    }
    physical_buses: list[int] = []
    candidates: list[JSONDict] = []
    selected_buses: list[int] = []
    for device in physical_roster.devices:
        candidate = _physical_entry(device)
        pci = device.identity.pci_bdf_full
        components = observed_pci_bdf_components(pci) if pci is not None else None
        if components is None or components[0] is None or components[3] is None:
            raise ValidationError("NvAPI projection requires every observed full physical PCI row.")
        if any(
            match_gpu_physical_identity(candidate, previous)
            in (GPUPhysicalBindingState.BOUND, GPUPhysicalBindingState.IDENTITY_CONFLICT)
            for previous in candidates
        ):
            raise StateError("NvAPI physical roster contains duplicate or conflicting identities.")
        relation = match_gpu_physical_identity(target_entry, candidate)
        if relation == GPUPhysicalBindingState.IDENTITY_CONFLICT:
            raise StateError(
                "NvAPI requested physical identity conflicts with its observed roster."
            )
        if relation == GPUPhysicalBindingState.BOUND:
            selected_buses.append(components[1])
        candidates.append(candidate)
        physical_buses.append(components[1])
    if len(selected_buses) != 1:
        raise StateError("NvAPI physical roster has no unique strong requested target.")
    binding = resolve_gpu_physical_binding(target_entry, candidates)
    if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
        raise StateError("NvAPI observed physical roster cannot establish the requested target.")
    native_buses = _read_native_buses(enumerate_gpus, read_bus)
    if Counter(physical_buses) != Counter(native_buses.values()):
        raise StateError("NvAPI and observed physical rosters have different bus coverage.")
    selected_bus = selected_buses[0]
    if physical_buses.count(selected_bus) != 1:
        raise StateError("NvAPI physical bus projection is ambiguous across actual PCI devices.")
    selected_handles = [handle for handle, bus in native_buses.items() if bus == selected_bus]
    if len(selected_handles) != 1:
        raise StateError("NvAPI native bus projection has no unique physical handle.")
    handle = ctypes.c_void_p(selected_handles[0])
    slot_id: int | None = None
    slot_status: int | None = None
    if read_slot is not None:
        slot = ctypes.c_uint32()
        slot_status = read_slot(handle, ctypes.pointer(slot))
        if not is_strict_int(slot_status):
            raise ValidationError("NvAPI auxiliary slot query status is invalid.")
        if slot_status == 0:
            slot_id = slot.value
    if _read_native_buses(enumerate_gpus, read_bus) != native_buses:
        raise StateError("NvAPI physical handle roster changed during acquisition.")
    return NvApiBoundDevice(binding.device, handle, selected_bus, slot_id, slot_status)


def _physical_entry(device: NvidiaCommandDevice) -> JSONDict:
    device.identity.validate_observations(device.pci_bdf_observations)
    candidate: JSONDict = {
        "type": "nvidia",
        "uuid": device.identity.uuid,
        "pci_bdf_full": device.identity.pci_bdf_full,
        "pci_bdf_observations": list(device.pci_bdf_observations),
    }
    read_gpu_physical_identity(candidate)
    return candidate


def _read_native_buses(
    enumerate_gpus: NvApiEnumPhysicalGpusFunctionProtocol,
    read_bus: NvApiBusFunctionProtocol,
) -> dict[int, int]:
    handles = (ctypes.c_void_p * 64)()
    count = ctypes.c_uint32()
    status = enumerate_gpus(handles, ctypes.pointer(count))
    _require_query_success(status, "physical_enumeration")
    if count.value > 64:
        raise ValidationError("NvAPI physical enumeration exceeds its actual native array.")
    native_buses: dict[int, int] = {}
    for index in range(count.value):
        handle_value = handles[index]
        if handle_value is None or handle_value == 0 or handle_value in native_buses:
            raise ValidationError("NvAPI physical enumeration returned null or duplicate handles.")
        bus = ctypes.c_uint32()
        status = read_bus(ctypes.c_void_p(handle_value), ctypes.pointer(bus))
        _require_query_success(status, "bus_query")
        if bus.value > 255:
            raise ValidationError("NvAPI bus query exceeds the observed PCI bus range.")
        native_buses[handle_value] = bus.value
    return native_buses


def _require_query_success(status: int, query: str) -> None:
    if not is_strict_int(status):
        raise ValidationError("NvAPI physical query status is invalid.")
    if status != 0:
        raise StateError(
            "NvAPI physical identity query failed.",
            details={"query": query, "native_status": status, "actuator_invoked": False},
        )


def acquire_nvapi_physical_roster(
    executor: CommandExecutorProtocol,
    *,
    executable: GpuExecutableResolution,
    enumerate_gpus: NvApiEnumPhysicalGpusFunctionProtocol,
    read_bus: NvApiBusFunctionProtocol,
) -> tuple[NvApiBoundDevice, ...]:
    physical = acquire_nvidia_command_roster(executor, executable=executable)
    candidates: list[JSONDict] = []
    buses: list[int] = []
    for row in physical.devices:
        candidate = _physical_entry(row)
        pci = row.identity.pci_bdf_full
        components = observed_pci_bdf_components(pci) if pci is not None else None
        if components is None or components[0] is None or components[3] is None:
            raise ValidationError("NvAPI full fleet requires every actual full PCI observation.")
        if any(
            match_gpu_physical_identity(candidate, previous)
            in (GPUPhysicalBindingState.BOUND, GPUPhysicalBindingState.IDENTITY_CONFLICT)
            for previous in candidates
        ):
            raise StateError("NvAPI full fleet contains conflicting physical observations.")
        candidates.append(candidate)
        buses.append(components[1])
    native = _read_native_buses(enumerate_gpus, read_bus)
    if Counter(buses) != Counter(native.values()):
        raise StateError("NvAPI full fleet lacks complete actual native bus coverage.")
    if len(set(buses)) != len(buses):
        raise StateError("NvAPI full fleet bus projection is ambiguous across physical devices.")
    bound: list[NvApiBoundDevice] = []
    for row, bus in zip(physical.devices, buses, strict=True):
        handles = tuple(handle for handle, actual in native.items() if actual == bus)
        if len(handles) != 1:
            raise StateError("NvAPI full fleet has no unique actual native handle.")
        device = GPUPhysicalDevice(
            create_device_id("gpu", row.command_locator),
            "nvidia",
            row.identity,
            None,
            None,
            row.pci_bdf_observations,
        )
        bound.append(NvApiBoundDevice(device, ctypes.c_void_p(handles[0]), bus, None, None))
    if _read_native_buses(enumerate_gpus, read_bus) != native:
        raise StateError("NvAPI full fleet changed during acquisition.")
    return tuple(bound)
