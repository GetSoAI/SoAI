"""SoAI - Complete bounded Linux kernel PCI observations [backend/hardware/gpu_inventory/linux_pci_sysfs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from collections.abc import Iterator

from core.concurrency.deadlines import deadline_after
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.files.directory_descriptor_scope import open_secure_directory_descriptor
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from hardware.gpu_inventory.drm_physical_observations import parse_drm_uevent
from hardware.gpu_inventory.linux_sysfs_scope import (
    open_sysfs_device_directory,
    read_sysfs_device_text,
)

__all__ = ("iter_linux_pci_sysfs_records",)


def iter_linux_pci_sysfs_records(sysfs_root: str) -> Iterator[dict[str, list[str]]]:
    root = os.path.realpath(sysfs_root)
    deadline = deadline_after(10.0)
    with open_secure_directory_descriptor(
        os.path.join(root, "bus", "pci", "devices"),
        unsupported_message="Linux PCI descriptor acquisition is unavailable.",
    ) as bus_descriptor:
        names = sorted(os.listdir(bus_descriptor))
        for name in names:
            if deadline.expired():
                raise SoAITimeoutError("Linux PCI sysfs acquisition deadline expired.")
            slot = normalize_observed_full_pci_bdf(name)
            if not slot:
                raise ValidationError("Linux PCI sysfs entry has no complete physical identity.")
            with open_sysfs_device_directory(
                bus_descriptor, name, devices_root=os.path.join(root, "devices")
            ) as (_, descriptor):
                facts = parse_drm_uevent(read_sysfs_device_text(descriptor, "uevent"))
                if normalize_observed_full_pci_bdf(facts.get("PCI_SLOT_NAME", "")) != slot:
                    raise ValidationError("Linux PCI sysfs slot observations conflict.")
                identity = facts.get("PCI_ID", "")
                class_value = facts.get("PCI_CLASS", "")
                if (
                    re.fullmatch(r"[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}", identity) is None
                    or re.fullmatch(r"[0-9A-Fa-f]{1,6}", class_value) is None
                ):
                    raise ValidationError("Linux PCI sysfs identity observations are malformed.")
                vendor, device = identity.lower().split(":")
                values = {"vendor": vendor, "device": device, "class": class_value}
                for attribute, expected in values.items():
                    if deadline.expired():
                        raise SoAITimeoutError("Linux PCI sysfs acquisition deadline expired.")
                    observed = read_sysfs_device_text(descriptor, attribute).strip()
                    if re.fullmatch(r"0x[0-9A-Fa-f]{4,6}", observed) is None or int(
                        observed, 16
                    ) != int(expected, 16):
                        raise ValidationError("Linux PCI sysfs identity observations conflict.")
                record = {
                    "Slot": [name],
                    "Class": [f"[{int(class_value, 16) >> 8:04x}]"],
                    "Vendor": [f"[{vendor}]"],
                    "Device": [f"PCI device [{device}]"],
                    "sysfs_uevent": ["\n".join(f"{key}={value}" for key, value in facts.items())],
                }
                driver = facts.get("DRIVER")
                if driver is not None:
                    record["Driver"] = [driver]
                if not os.path.samestat(os.fstat(descriptor), os.stat(name, dir_fd=bus_descriptor)):
                    raise ValidationError(
                        "Linux PCI sysfs device relation changed during acquisition."
                    )
            yield record
        if deadline.expired():
            raise SoAITimeoutError("Linux PCI sysfs acquisition deadline expired.")
        if sorted(os.listdir(bus_descriptor)) != names:
            raise ValidationError("Linux PCI sysfs inventory changed during acquisition.")
