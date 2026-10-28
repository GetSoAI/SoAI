"""SoAI - Anchored ADL physical roster relations [backend/hardware/vendors/amd/adl_physical_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_identity_normalization import (
    normalize_windows_pnp_instance_id,
    observed_pci_bdf_conflicts,
)
from core.hardware.gpu_physical_identity import GPUInventoryReadState, GPUPhysicalDevice
from core.hardware.gpu_physical_observations import read_gpu_physical_identity
from core.types.json import JSONDict
from hardware.gpu_inventory.windows_adapters import (
    build_windows_gpu_entry,
    coerce_windows_gpu_name,
    detect_windows_adapter_vendor,
)
from hardware.gpu_inventory.windows_physical_acquisition import read_windows_physical_acquisition
from hardware.vendors.amd.adl_abi import AdlAdapterObservation

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from hardware.vendors.amd.adl_session import AdlSession

__all__ = ("AdlPhysicalDevice", "acquire_adl_physical_devices")


@dataclass(frozen=True, slots=True)
class AdlPhysicalDevice:
    device: GPUPhysicalDevice
    adapters: tuple[AdlAdapterObservation, ...]


def acquire_adl_physical_devices(
    session: AdlSession, executor: CommandExecutorProtocol
) -> tuple[AdlPhysicalDevice, ...]:
    cim = read_windows_physical_acquisition(executor)
    if cim.state != GPUInventoryReadState.OBSERVED or not cim.records:
        raise StateError(
            "ADL requires a complete fresh Windows physical acquisition.",
            details={"observation_state": cim.state.value, "reason_code": cim.reason_code},
        )
    groups: dict[str, list[AdlAdapterObservation]] = {}
    roster = tuple(dict.fromkeys(session.read_adapters()))
    for adapter in roster:
        if adapter.vendor != 1002 or not adapter.exists:
            continue
        pnp = normalize_windows_pnp_instance_id(adapter.pnp_instance)
        if not pnp:
            raise ValidationError("ADL actual AMD roster has no complete PNP instance authority.")
        if pnp not in groups:
            groups[pnp] = []
        groups[pnp].append(adapter)
    entries: list[JSONDict] = []
    cim_instances: set[str] = set()
    for index, row in enumerate(cim.records):
        name = coerce_windows_gpu_name(row.get("Name"))
        if detect_windows_adapter_vendor(row, name) == "amd":
            entry = build_windows_gpu_entry(
                gpu_info=row, gpu_index=index, vendor="amd", vendor_id=None, name=name
            )
            identity = read_gpu_physical_identity(entry)
            if identity is None or identity.windows_pnp_instance_id is None:
                raise ValidationError(
                    "Windows actual AMD row has no complete PNP instance authority."
                )
            entries.append(entry)
            cim_instances.add(identity.windows_pnp_instance_id)
    groups = _anchor_logical_rows(groups, entries, cim_instances)
    devices: list[AdlPhysicalDevice] = []
    for entry in entries:
        identity = read_gpu_physical_identity(entry)
        if identity is None or identity.windows_pnp_instance_id is None:
            raise ValidationError("ADL physical fleet lost its observed PNP authority.")
        if identity.windows_pnp_instance_id not in groups:
            continue

        def adapter_order(
            row: AdlAdapterObservation, instance: str = identity.windows_pnp_instance_id
        ) -> tuple[bool, int]:
            return (
                normalize_windows_pnp_instance_id(row.pnp_instance) != instance,
                row.adapter_index,
            )

        adapters = tuple(sorted(groups[identity.windows_pnp_instance_id], key=adapter_order))
        addresses = {(row.bus, row.device, row.function) for row in adapters}
        if len(addresses) != 1:
            raise ValidationError(
                "ADL logical aliases conflict with their actual physical locator."
            )
        observations = tuple(
            dict.fromkeys(f"{row.bus:02x}:{row.device:02x}.{row.function}" for row in adapters)
        )
        device_id = entry["device_id"]
        if not isinstance(device_id, str):
            raise ValidationError("ADL physical fleet has no observed canonical device identifier.")
        devices.append(
            AdlPhysicalDevice(
                GPUPhysicalDevice(
                    device_id, "amd", identity, None, adapters[0].adapter_index, observations
                ),
                adapters,
            )
        )
    if roster != tuple(dict.fromkeys(session.read_adapters())):
        raise StateError("ADL native fleet changed during physical observation.")
    return tuple(devices)


def _anchor_logical_rows(
    groups: dict[str, list[AdlAdapterObservation]],
    entries: list[JSONDict],
    cim_instances: set[str],
) -> dict[str, list[AdlAdapterObservation]]:
    anchors = {
        instance: list(rows) for instance, rows in groups.items() if instance in cim_instances
    }
    anchor_addresses: dict[str, tuple[int, int, int]] = {}
    for instance, rows in anchors.items():
        addresses = {(row.bus, row.device, row.function) for row in rows}
        if len(addresses) != 1:
            raise ValidationError("ADL physical anchor has contradictory native locators.")
        address = next(iter(addresses))
        if address in anchor_addresses.values():
            raise ValidationError("ADL physical anchors share a conflicting native locator.")
        anchor_addresses[instance] = address
        native_bdf = f"{address[0]:02x}:{address[1]:02x}.{address[2]}"
        for entry in entries:
            bdf = entry.get("pci_bdf_full")
            if not isinstance(bdf, str):
                continue
            if entry.get("windows_pnp_instance_id") == instance:
                if observed_pci_bdf_conflicts(native_bdf, bdf):
                    raise ValidationError("ADL physical anchor contradicts fresh CIM locator.")
            elif not observed_pci_bdf_conflicts(native_bdf, bdf):
                raise ValidationError("ADL native locator has competing CIM physical authority.")
    for instance, rows in groups.items():
        if instance in anchors:
            continue
        addresses = {(row.bus, row.device, row.function) for row in rows}
        hardware = _pci_operands(instance)
        candidates = [
            anchor
            for anchor, address in anchor_addresses.items()
            if addresses == {address}
            and all(
                hardware[key] == value
                for key, value in _pci_operands(anchor).items()
                if key in hardware
            )
        ]
        if len(candidates) != 1:
            raise StateError("ADL logical row has no unique proved Windows physical anchor.")
        anchors[candidates[0]].extend(rows)
    return anchors


def _pci_operands(instance: str) -> dict[str, str]:
    operands: dict[str, str] = {}
    for token in instance.split("\\")[1].split("&"):
        name, separator, value = token.partition("_")
        if separator and name in ("VEN", "DEV", "SUBSYS", "REV"):
            if name in operands and operands[name] != value:
                raise ValidationError("ADL PCI identity has contradictory native operands.")
            operands[name] = value
    return operands
