"""SoAI - Fresh physical NVIDIA architecture observations under the existing NVML gate [backend/hardware/vendors/nvidia/architecture_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_architecture import (
    NvidiaArchitectureObservation,
    NvidiaArchitectureReadState,
    NvidiaArchitectureSnapshot,
    nvidia_architecture_row_observation,
)
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import (
    GPUInventoryReadState,
    GPUPhysicalDevice,
    GPUPhysicalIdentity,
)
from core.hardware.protocols import NvmlGateProtocol
from core.system.protocols import CommandExecutorProtocol
from core.validation.strict_numbers import require_int_in_range_strict
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_inventory.identity import uuid_from_device_id
from hardware.gpu_inventory.physical_snapshot import acquire_gpu_physical_snapshot
from hardware.vendors.nvidia.internal_protocols import (
    NvmlArchitectureModuleProtocol,
    NvmlErrorValueProtocol,
)
from hardware.vendors.nvidia.nvml import pynvml_module

if TYPE_CHECKING:
    from types import ModuleType

    from core.types.json import JSONDict
    from hardware.vendors.nvidia.internal_protocols import NvmlDeviceHandle


__all__ = (
    "NvidiaArchitectureReaderDependencies",
    "NvidiaArchitectureReader",
    "read_nvidia_architecture_target",
    "read_nvidia_scan_architecture",
)


@dataclass(frozen=True, slots=True)
class NvidiaArchitectureReaderDependencies:
    gate: NvmlGateProtocol

    def __post_init__(self) -> None:
        require_dependencies(owner="NvidiaArchitectureReaderDependencies", gate=self.gate)


class NvidiaArchitectureReader:
    def __init__(self, deps: NvidiaArchitectureReaderDependencies) -> None:
        self._gate = deps.gate

    async def read_architectures(
        self, *, command_executor: CommandExecutorProtocol, acquisition_id: str
    ) -> NvidiaArchitectureSnapshot:
        return await run_joined_thread_call(
            self._read_snapshot,
            command_executor,
            acquisition_id,
            task_name="nvidia-physical-architecture-observation",
            retain_resources_until_complete=True,
        )

    def _read_snapshot(
        self, executor: CommandExecutorProtocol, acquisition_id: str
    ) -> NvidiaArchitectureSnapshot:
        physical = acquire_gpu_physical_snapshot(
            executor, runtime_platform=self._gate.runtime_platform, acquisition_id=acquisition_id
        )
        targets = tuple(device for device in physical.devices if device.vendor == "nvidia")
        if len(physical.devices) > 256:
            raise ValidationError(
                "NVIDIA architecture observation requires bounded physical scope."
            )
        scope = tuple(row for row in physical.vendors if row.vendor == "nvidia")
        if len(scope) != 1 or scope[0].state != GPUInventoryReadState.OBSERVED:
            return NvidiaArchitectureSnapshot(physical, ())
        module = pynvml_module
        if not self._gate.nvml_available or module is None:
            return NvidiaArchitectureSnapshot(
                physical,
                tuple(
                    _unobserved(
                        target,
                        NvidiaArchitectureReadState.RUNTIME_UNAVAILABLE,
                        "nvml_runtime_unavailable",
                    )
                    for target in targets
                ),
            )
        if not isinstance(module, NvmlArchitectureModuleProtocol):
            return NvidiaArchitectureSnapshot(
                physical,
                tuple(
                    _unobserved(
                        target,
                        NvidiaArchitectureReadState.QUERY_UNAVAILABLE,
                        "nvml_architecture_query_unavailable",
                    )
                    for target in targets
                ),
            )
        if not targets:
            return NvidiaArchitectureSnapshot(physical, ())
        try:
            with self._gate.session():
                observations = tuple(
                    read_nvidia_architecture_target(module, target) for target in targets
                )
        except module.NVMLError as exception:
            state, reason = _nvml_failure(exception)
            observations = tuple(_unobserved(target, state, reason) for target in targets)
        return NvidiaArchitectureSnapshot(physical, observations)


def _unobserved(
    target: GPUPhysicalDevice, state: NvidiaArchitectureReadState, reason: str
) -> NvidiaArchitectureObservation:
    return NvidiaArchitectureObservation(target, state, None, reason)


def _native_text(value: str | bytes) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "strict")
    return require_canonical_trimmed_json_text(
        value, error_message="NVML physical identity is invalid."
    )


def _read_identity(
    module: NvmlArchitectureModuleProtocol, handle: NvmlDeviceHandle
) -> GPUPhysicalIdentity:
    pci = normalize_observed_full_pci_bdf(_native_text(module.nvmlDeviceGetPciInfo(handle).busId))
    if not pci:
        raise ValidationError("NVML PCI identity lacks an observed full domain and function.")
    return GPUPhysicalIdentity(_native_text(module.nvmlDeviceGetUUID(handle)), pci)


def read_nvidia_scan_architecture(
    module: ModuleType,
    *,
    device_id: str,
    device_index: int,
    pci_bdf_full: str | None,
    pci_bdf_observations: list[str],
) -> JSONDict:
    try:
        target = GPUPhysicalDevice(
            device_id=device_id,
            vendor="nvidia",
            identity=GPUPhysicalIdentity(uuid_from_device_id(device_id), pci_bdf_full),
            gpu_index=device_index,
            vendor_index=device_index,
            pci_bdf_observations=tuple(pci_bdf_observations),
        )
    except ValidationError:
        return {
            "state": NvidiaArchitectureReadState.IDENTITY_CONFLICT.value,
            "reason": "physical_identity_invalid",
        }
    if not isinstance(module, NvmlArchitectureModuleProtocol):
        observation = _unobserved(
            target,
            NvidiaArchitectureReadState.QUERY_UNAVAILABLE,
            "nvml_architecture_query_unavailable",
        )
    else:
        try:
            observation = read_nvidia_architecture_target(module, target)
        except StateError:
            observation = _unobserved(
                target,
                NvidiaArchitectureReadState.INVALID_RESPONSE,
                "nvml_architecture_status_unexpected",
            )
    return nvidia_architecture_row_observation(observation)


def read_nvidia_architecture_target(
    module: NvmlArchitectureModuleProtocol, target: GPUPhysicalDevice
) -> NvidiaArchitectureObservation:
    pci = normalize_observed_full_pci_bdf(target.identity.pci_bdf_full or "")
    if not pci:
        return _unobserved(
            target, NvidiaArchitectureReadState.IDENTITY_CONFLICT, "physical_pci_unproved"
        )
    try:
        handle = module.nvmlDeviceGetHandleByPciBusId(pci)
        if not handle:
            raise ValidationError("NVML PCI lookup returned no native handle.")
        before = _read_identity(module, handle)
        if before.pci_bdf_full != pci or (
            target.identity.uuid is not None
            and (before.uuid is None or target.identity.uuid.casefold() != before.uuid.casefold())
        ):
            return _unobserved(
                target,
                NvidiaArchitectureReadState.IDENTITY_CONFLICT,
                "nvml_physical_identity_conflict",
            )
        code = require_int_in_range_strict(
            module.nvmlDeviceGetArchitecture(handle),
            minimum=0,
            maximum=4294967295,
            error_message="NVML architecture is not an unsigned 32-bit native value.",
        )
        if _read_identity(module, handle) != before:
            return _unobserved(
                target,
                NvidiaArchitectureReadState.IDENTITY_CONFLICT,
                "nvml_physical_identity_changed",
            )
        return NvidiaArchitectureObservation(
            target, NvidiaArchitectureReadState.OBSERVED, code, native_identity=before
        )
    except (ValidationError, UnicodeError):
        return _unobserved(
            target,
            NvidiaArchitectureReadState.INVALID_RESPONSE,
            "nvml_architecture_response_invalid",
        )
    except module.NVMLError as exception:
        state, reason = _nvml_failure(exception)
        return _unobserved(target, state, reason)


def _nvml_failure(exception: Exception) -> tuple[NvidiaArchitectureReadState, str]:
    if not isinstance(exception, NvmlErrorValueProtocol):
        raise StateError("NVML architecture failure lacks a native status.") from exception
    status = require_int_in_range_strict(
        exception.value,
        minimum=0,
        maximum=4294967295,
        error_message="NVML architecture failure status is invalid.",
    )
    if status in (3, 4, 13):
        return NvidiaArchitectureReadState.QUERY_UNAVAILABLE, f"nvml_query_status_{status}"
    if status in (6, 15, 28):
        return NvidiaArchitectureReadState.DEVICE_UNAVAILABLE, f"nvml_device_status_{status}"
    if status in (1, 9, 12, 18):
        return NvidiaArchitectureReadState.RUNTIME_UNAVAILABLE, f"nvml_runtime_status_{status}"
    if status == 2:
        return NvidiaArchitectureReadState.INVALID_RESPONSE, "nvml_invalid_argument"
    raise StateError(
        "NVIDIA architecture query failed with an unexpected native status.",
        details={"native_status": status},
    ) from exception
