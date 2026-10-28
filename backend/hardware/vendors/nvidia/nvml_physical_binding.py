"""SoAI - Fresh NVML physical handle binding [backend/hardware/vendors/nvidia/nvml_physical_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
    GPUPhysicalIdentity,
    gpu_physical_device_observations,
)
from core.hardware.gpu_physical_observations import read_gpu_physical_identity
from core.validation.strict_integer import is_strict_int
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_inventory.physical_binding import (
    match_gpu_physical_identity,
    resolve_gpu_physical_binding,
)
from hardware.vendors.nvidia.internal_protocols import NvmlErrorValueProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.vendors.nvidia.internal_protocols import (
        NvmlDeviceHandle,
        NvmlIdentityModuleProtocol,
    )


__all__ = (
    "NvmlBoundDevice",
    "NvmlObservedDevice",
    "acquire_nvml_physical_roster",
    "acquire_nvml_physical_binding",
    "revalidate_nvml_bound_device",
)


@dataclass(frozen=True, slots=True)
class NvmlBoundDevice:
    device: GPUPhysicalDevice
    handle: NvmlDeviceHandle
    native_index: int


@dataclass(frozen=True, slots=True)
class NvmlObservedDevice:
    handle: NvmlDeviceHandle
    native_index: int
    identity: GPUPhysicalIdentity
    pci_bdf_observations: tuple[str, ...]


def acquire_nvml_physical_roster(
    module: NvmlIdentityModuleProtocol,
) -> tuple[NvmlObservedDevice, ...]:
    count = _read_device_count(module)
    observations: list[NvmlObservedDevice] = []
    candidates: list[JSONDict] = []
    for native_index in range(count):
        handle = module.nvmlDeviceGetHandleByIndex(native_index)
        if handle is None or not handle:
            raise ValidationError("NVML returned an unavailable native handle.")
        candidate = _read_native_identity(module, handle)
        candidate["vendor_id"] = native_index
        identity = read_gpu_physical_identity(candidate)
        if identity is None:
            raise StateError("NVML identity roster is incomplete.")
        if any(
            match_gpu_physical_identity(candidate, previous)
            in (GPUPhysicalBindingState.BOUND, GPUPhysicalBindingState.IDENTITY_CONFLICT)
            for previous in candidates
        ):
            raise StateError("NVML identity roster contains duplicate or conflicting devices.")
        pci = candidate["pci_bdf_observations"]
        if not isinstance(pci, list) or any(not isinstance(value, str) for value in pci):
            raise ValidationError("NVML actual PCI observations are invalid.")
        observations.append(
            NvmlObservedDevice(
                handle,
                native_index,
                identity,
                tuple(value for value in pci if isinstance(value, str)),
            )
        )
        candidates.append(candidate)
    if _read_device_count(module) != count:
        raise StateError("NVML identity roster changed during acquisition.")
    return tuple(observations)


def acquire_nvml_physical_binding(
    module: NvmlIdentityModuleProtocol, *, target: GPUPhysicalDevice
) -> NvmlBoundDevice:
    if target.vendor.casefold() != "nvidia":
        raise ValidationError("NVML binding requires a NVIDIA physical target.")
    roster = acquire_nvml_physical_roster(module)
    candidates: list[JSONDict] = [
        {
            "type": "nvidia",
            "uuid": row.identity.uuid,
            "pci_bdf_observations": list(row.pci_bdf_observations),
            "vendor_id": row.native_index,
        }
        for row in roster
    ]
    binding = resolve_gpu_physical_binding(gpu_physical_device_observations(target), candidates)
    device = binding.device
    if binding.state != GPUPhysicalBindingState.BOUND or device is None:
        raise StateError(
            "NVML physical target could not be bound.",
            details={"binding_state": binding.state.value, "reason": binding.reason_code},
        )
    selected_index = device.vendor_index
    if selected_index is None or not 0 <= selected_index < len(roster):
        raise ValidationError("NVML physical binding has no proved native locator.")
    return NvmlBoundDevice(device, roster[selected_index].handle, selected_index)


def revalidate_nvml_bound_device(
    module: NvmlIdentityModuleProtocol, bound: NvmlBoundDevice
) -> None:
    current = _read_native_identity(module, bound.handle)
    relation = match_gpu_physical_identity(gpu_physical_device_observations(bound.device), current)
    if relation != GPUPhysicalBindingState.BOUND:
        raise StateError(
            "NVML bound handle no longer identifies its prepared physical device.",
            details={"binding_state": relation.value},
        )


def _read_device_count(module: NvmlIdentityModuleProtocol) -> int:
    count = module.nvmlDeviceGetCount()
    if not is_strict_int(count) or count < 0:
        raise ValidationError("NVML device count is invalid.")
    return count


def _read_native_identity(module: NvmlIdentityModuleProtocol, handle: NvmlDeviceHandle) -> JSONDict:
    candidate: JSONDict = {"type": "nvidia", "pci_bdf_observations": []}
    try:
        unsupported_error = module.NVMLError_NotSupported
    except AttributeError:
        unsupported_errors: tuple[type[Exception], ...] = ()
    else:
        if not isinstance(unsupported_error, type) or not issubclass(unsupported_error, Exception):
            raise ValidationError("NVML unsupported-query exception contract is invalid.")
        unsupported_errors = (unsupported_error,)
    try:
        get_uuid = module.nvmlDeviceGetUUID
    except AttributeError:
        get_uuid = None
    if get_uuid is not None:
        try:
            candidate["uuid"] = _native_text(get_uuid(handle), "UUID")
        except unsupported_errors as exception:
            _validate_unsupported_query(module, exception)
            candidate["uuid"] = None
    try:
        get_pci = module.nvmlDeviceGetPciInfo
    except AttributeError:
        get_pci = None
    if get_pci is not None:
        try:
            candidate["pci_bdf_observations"] = [_native_text(get_pci(handle).busId, "PCI")]
        except unsupported_errors as exception:
            _validate_unsupported_query(module, exception)
            candidate["pci_bdf_observations"] = []
    read_gpu_physical_identity(candidate)
    return candidate


def _validate_unsupported_query(module: NvmlIdentityModuleProtocol, exception: Exception) -> None:
    if not isinstance(exception, NvmlErrorValueProtocol):
        raise exception
    try:
        status = exception.value
        unsupported_status = module.NVML_ERROR_NOT_SUPPORTED
    except AttributeError as missing_status:
        raise exception from missing_status
    if (
        not is_strict_int(status)
        or not is_strict_int(unsupported_status)
        or unsupported_status != 3
        or status != unsupported_status
    ):
        raise exception


def _native_text(value: str | bytes, label: str) -> str:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exception:
            raise ValidationError(f"NVML {label} observation is not valid UTF-8.") from exception
    return require_canonical_trimmed_json_text(
        value, error_message=f"NVML {label} observation is invalid."
    )
