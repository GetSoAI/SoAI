"""SoAI - Actual NVIDIA settings physical roster and GPU targeting [backend/hardware/vendors/nvidia/settings_physical_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
    GPUPhysicalIdentity,
)
from core.types.json import JSONDict
from core.validation.strict_numbers import require_int_in_range_strict
from hardware.gpu_inventory.physical_binding import (
    match_gpu_physical_identity,
    resolve_gpu_physical_binding,
)
from hardware.vendors.nvidia.settings_control_queries import (
    NvidiaSettingsSession,
    parse_settings_attribute,
    query_settings_output,
)

__all__ = (
    "NvidiaSettingsObservedDevice",
    "NvidiaSettingsBoundDevice",
    "acquire_settings_physical_roster",
    "acquire_settings_physical_binding",
)


@dataclass(frozen=True, slots=True)
class NvidiaSettingsObservedDevice:
    native_gpu_id: int
    identity: GPUPhysicalIdentity
    pci_bdf_observations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NvidiaSettingsBoundDevice:
    device: GPUPhysicalDevice
    native_gpu_id: int


def acquire_settings_physical_roster(
    session: NvidiaSettingsSession,
) -> tuple[NvidiaSettingsObservedDevice, ...]:
    output = query_settings_output(session, "gpus")
    counts = re.findall(r"(?m)^\s*(\d+) GPUs? on [^\n]+$", output)
    rows = re.findall(r"(?m)^\s*\[(\d+)\].*\[gpu:(\d+)\][^\n]*$", output)
    if len(counts) != 1 or int(counts[0]) != len(rows) or output.count("[gpu:") != len(rows):
        raise ValidationError("NVIDIA settings native GPU roster coverage is incomplete.")
    native_ids = tuple(int(row[1]) for row in rows)
    if len(set(native_ids)) != len(native_ids):
        raise ValidationError("NVIDIA settings native GPU targets are duplicated.")
    devices: list[NvidiaSettingsObservedDevice] = []
    candidates: list[JSONDict] = []
    blocks = re.split(r"(?m)^\s*\[\d+\].*\[gpu:\d+\][^\n]*$", output)[1:]
    for native_id, block in zip(native_ids, blocks, strict=True):
        uuid_names = tuple(
            name
            for name in re.findall(r"(?m)^\s*(GPU-[A-Za-z0-9-]+)\s*$", block)
            if not re.fullmatch(r"GPU-\d+", name)
        )
        if len(uuid_names) > 1:
            raise ValidationError("NVIDIA settings native UUID names are ambiguous.")
        uuid = uuid_names[0] if uuid_names else None
        components: dict[str, int] = {}
        for attribute, maximum in (
            ("PCIDomain", 0xFFFFFFFF),
            ("PCIBus", 0xFF),
            ("PCIDevice", 0x1F),
            ("PCIFunc", 7),
        ):
            observed = parse_settings_attribute(
                query_settings_output(session, f"[gpu:{native_id}]/{attribute}"),
                attribute=attribute,
                target_type="gpu",
                target_id=native_id,
            )
            components[attribute] = require_int_in_range_strict(
                observed.value,
                minimum=0,
                maximum=maximum,
                error_message="NVIDIA settings actual PCI component is invalid.",
            )
        domain = components["PCIDomain"]
        width = 4 if domain <= 0xFFFF else 8
        pci = (
            f"{domain:0{width}x}:{components['PCIBus']:02x}:"
            f"{components['PCIDevice']:02x}.{components['PCIFunc']:x}"
        )
        identity = GPUPhysicalIdentity(uuid, pci)
        candidate: JSONDict = {
            "type": "nvidia",
            "uuid": uuid,
            "pci_bdf_full": pci,
            "pci_bdf_observations": [pci],
        }
        if any(
            match_gpu_physical_identity(candidate, previous)
            in (GPUPhysicalBindingState.BOUND, GPUPhysicalBindingState.IDENTITY_CONFLICT)
            for previous in candidates
        ):
            raise StateError("NVIDIA settings native roster contains conflicting physical devices.")
        candidates.append(candidate)
        devices.append(NvidiaSettingsObservedDevice(native_id, identity, (pci,)))
    return tuple(devices)


def acquire_settings_physical_binding(
    session: NvidiaSettingsSession, *, target: GPUPhysicalDevice
) -> NvidiaSettingsBoundDevice:
    if target.vendor.casefold() != "nvidia":
        raise ValidationError("NVIDIA settings binding requires its actual NVIDIA target.")
    roster = acquire_settings_physical_roster(session)
    selected: JSONDict = {
        "device_id": target.device_id,
        "type": target.vendor,
        "uuid": target.identity.uuid,
        "pci_bdf_full": target.identity.pci_bdf_full,
        "pci_bdf_observations": list(target.pci_bdf_observations),
    }
    candidates: list[JSONDict] = [
        {
            "type": "nvidia",
            "uuid": device.identity.uuid,
            "pci_bdf_full": device.identity.pci_bdf_full,
            "pci_bdf_observations": list(device.pci_bdf_observations),
        }
        for device in roster
    ]
    binding = resolve_gpu_physical_binding(selected, candidates)
    if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
        raise StateError("NVIDIA settings physical target is unproved or contradictory.")
    matched = [
        device
        for device, candidate in zip(roster, candidates, strict=True)
        if match_gpu_physical_identity(selected, candidate) == GPUPhysicalBindingState.BOUND
    ]
    if len(matched) != 1:
        raise StateError("NVIDIA settings native target relation is ambiguous.")
    return NvidiaSettingsBoundDevice(binding.device, matched[0].native_gpu_id)
