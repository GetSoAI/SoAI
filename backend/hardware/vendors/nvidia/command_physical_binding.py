"""SoAI - Fresh NVIDIA command physical identity [backend/hardware/vendors/nvidia/command_physical_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
    GPUPhysicalIdentity,
)
from core.hardware.gpu_physical_observations import read_gpu_physical_identity
from core.system.commands import require_command_result
from hardware.gpu_inventory.executable_resolution import GpuExecutableState
from hardware.gpu_inventory.physical_binding import (
    match_gpu_physical_identity,
    resolve_gpu_physical_binding,
)

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.gpu_inventory.executable_resolution import GpuExecutableResolution


__all__ = (
    "NvidiaCommandDevice",
    "NvidiaCommandRoster",
    "NvidiaCommandBoundDevice",
    "acquire_nvidia_command_roster",
    "acquire_nvidia_command_binding",
)


@dataclass(frozen=True, slots=True)
class NvidiaCommandDevice:
    identity: GPUPhysicalIdentity
    pci_bdf_observations: tuple[str, ...]
    command_locator: str


@dataclass(frozen=True, slots=True)
class NvidiaCommandRoster:
    devices: tuple[NvidiaCommandDevice, ...]


@dataclass(frozen=True, slots=True)
class NvidiaCommandBoundDevice:
    device: GPUPhysicalDevice
    command_locator: str


def acquire_nvidia_command_roster(
    executor: CommandExecutorProtocol, *, executable: GpuExecutableResolution
) -> NvidiaCommandRoster:
    if executable.executable != "nvidia-smi":
        raise ValidationError("NVIDIA identity query requires the nvidia-smi executable authority.")
    path = executable.path
    if executable.state != GpuExecutableState.FOUND or path is None:
        raise StateError(
            "NVIDIA identity query requires an available trusted executable.",
            details={"executable_state": executable.state.value},
        )
    result = executor.execute(
        [path, "--query-gpu=uuid,pci.bus_id", "--format=csv,noheader,nounits"],
        timeout=5,
        shell=False,
        use_sudo=False,
    )
    require_command_result(result, error_message="NVIDIA identity query response is invalid.")
    if result.return_code != 0:
        raise StateError(
            "NVIDIA identity query failed.",
            details={
                "return_code": result.return_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )
    devices: list[NvidiaCommandDevice] = []
    candidates: list[JSONDict] = []
    try:
        for raw_row in csv.reader(io.StringIO(result.stdout), strict=True):
            if not raw_row or all(not value.strip() for value in raw_row):
                continue
            if len(raw_row) != 2:
                raise ValidationError("NVIDIA identity roster contains an invalid row.")
            uuid = _observed_namespace(raw_row[0])
            pci = _observed_namespace(raw_row[1])
            candidate: JSONDict = {
                "type": "nvidia",
                "uuid": uuid,
                "pci_bdf_observations": [pci] if pci is not None else [],
            }
            identity = read_gpu_physical_identity(candidate)
            if identity is None:
                raise ValidationError("NVIDIA identity roster contains an unidentifiable device.")
            if any(
                match_gpu_physical_identity(candidate, previous)
                in (GPUPhysicalBindingState.BOUND, GPUPhysicalBindingState.IDENTITY_CONFLICT)
                for previous in candidates
            ):
                raise StateError(
                    "NVIDIA identity roster contains duplicate or conflicting devices."
                )
            locator = uuid or identity.pci_bdf_full
            if locator is None:
                raise ValidationError("NVIDIA identity query did not establish a physical locator.")
            devices.append(
                NvidiaCommandDevice(identity, (pci,) if pci is not None else (), locator)
            )
            candidates.append(candidate)
    except csv.Error as exception:
        raise ValidationError("NVIDIA identity roster contains malformed CSV.") from exception
    return NvidiaCommandRoster(tuple(devices))


def acquire_nvidia_command_binding(
    executor: CommandExecutorProtocol,
    *,
    target: GPUPhysicalDevice,
    executable: GpuExecutableResolution,
) -> NvidiaCommandBoundDevice:
    if target.vendor.casefold() != "nvidia":
        raise ValidationError("NVIDIA command binding requires a NVIDIA physical target.")
    roster = acquire_nvidia_command_roster(executor, executable=executable)
    selected: JSONDict = {
        "device_id": target.device_id,
        "type": target.vendor,
        "uuid": target.identity.uuid,
        "pci_bdf_full": target.identity.pci_bdf_full,
        "pci_bdf_observations": list(target.pci_bdf_observations),
    }
    candidates = [_device_entry(device) for device in roster.devices]
    binding = resolve_gpu_physical_binding(selected, candidates)
    if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
        raise StateError(
            "NVIDIA command physical target could not be bound.",
            details={"binding_state": binding.state.value, "reason": binding.reason_code},
        )
    for device, candidate in zip(roster.devices, candidates, strict=True):
        if match_gpu_physical_identity(selected, candidate) == GPUPhysicalBindingState.BOUND:
            return NvidiaCommandBoundDevice(binding.device, device.command_locator)
    raise StateError("NVIDIA command binding has no proved physical locator.")


def _observed_namespace(value: str) -> str | None:
    text = value.strip()
    return None if not text or text.casefold() in {"n/a", "[not supported]"} else text


def _device_entry(device: NvidiaCommandDevice) -> JSONDict:
    return {
        "type": "nvidia",
        "uuid": device.identity.uuid,
        "pci_bdf_full": device.identity.pci_bdf_full,
        "pci_bdf_observations": list(device.pci_bdf_observations),
    }
