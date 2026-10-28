"""SoAI - Observed PCI graphics function relationships [backend/hardware/gpu_inventory/pci_function_relationships.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.hardware.gpu_identity_normalization import observed_pci_bdf_components

if TYPE_CHECKING:
    from hardware.gpu_inventory.linux_physical_acquisition import LinuxPciGpuRecord


__all__ = (
    "PciFunctionRelationship",
    "read_pci_function_relationship",
)


@dataclass(frozen=True, slots=True)
class PciFunctionRelationship:
    state: str
    primary_slot: str | None


_SECONDARY_PAIRS = (
    ("8086", "2772", "2776", "i915"),
    ("8086", "2a42", "2a43", "i915"),
    ("8086", "27ae", "27a6", "i915"),
    ("1002", "5b60", "5b70", "radeon"),
)


def read_pci_function_relationship(
    record: LinuxPciGpuRecord, records: list[LinuxPciGpuRecord], drm_pci_slots: tuple[str, ...]
) -> PciFunctionRelationship:
    for vendor_id, primary_id, secondary_id, primary_driver in _SECONDARY_PAIRS:
        if record.pci_vendor_id != vendor_id or record.pci_device_id != secondary_id:
            continue
        components = observed_pci_bdf_components(record.slot)
        if (
            components is None
            or components[3] != 1
            or record.kernel_driver is not None
            or record.pci_class_id != "0380"
        ):
            return PciFunctionRelationship("unresolved", None)
        candidates: list[LinuxPciGpuRecord] = []
        for peer in records:
            peer_components = observed_pci_bdf_components(peer.slot)
            same_primary_slot = (
                peer_components is not None
                and peer_components[:3] == components[:3]
                and peer_components[3] == 0
            )
            supported_primary = (
                peer.pci_vendor_id == vendor_id
                and peer.pci_device_id == primary_id
                and peer.kernel_driver == primary_driver
                and peer.pci_class_id in ("0300", "0380")
            )
            primary_owned = any(
                observed_pci_bdf_components(slot) == peer_components for slot in drm_pci_slots
            )
            secondary_owned = any(
                observed_pci_bdf_components(slot) == components for slot in drm_pci_slots
            )
            if same_primary_slot and supported_primary and primary_owned and not secondary_owned:
                candidates.append(peer)
        if len(candidates) == 1:
            return PciFunctionRelationship("secondary", candidates[0].slot)
        return PciFunctionRelationship("unresolved", None)
    return PciFunctionRelationship("independent", None)
