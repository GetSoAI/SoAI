"""SoAI - Physically verified legacy radeon GEM capacity [backend/hardware/vendors/amd/radeon_memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import errno
import os

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_text
from core.hardware.gpu_identity_normalization import (
    normalize_observed_full_pci_bdf,
    observed_pci_bdf_components,
)
from hardware.gpu_inventory.drm_physical_observations import parse_drm_uevent, read_drm_primary_node

__all__ = ("read_radeon_memory_capacity",)


class RadeonGemInfo(ctypes.Structure):
    _fields_ = (
        ("gart_bytes", ctypes.c_uint64),
        ("vram_bytes", ctypes.c_uint64),
        ("visible_vram_bytes", ctypes.c_uint64),
    )


def read_radeon_memory_capacity(device_path: str, pci_bdf: str) -> int | None:
    address = observed_pci_bdf_components(pci_bdf)
    if address is None or address[0] is None or address[3] is None:
        raise ValidationError("Radeon memory acquisition requires a full physical PCI locator.")
    with open_text(os.path.join(device_path, "uevent"), encoding="utf-8") as handle:
        fields = parse_drm_uevent(handle.read(4096))
    if (
        fields.get("DRIVER") != "radeon"
        or fields.get("PCI_ID", "").split(":")[0].lower() != "1002"
        or normalize_observed_full_pci_bdf(fields.get("PCI_SLOT_NAME", ""))
        != normalize_observed_full_pci_bdf(pci_bdf)
        or os.path.basename(os.path.realpath(os.path.join(device_path, "driver"))) != "radeon"
    ):
        raise ValidationError("Radeon GEM acquisition has no native driver authority.")
    _, device_number = read_drm_primary_node(device_path)
    library = ctypes.CDLL("libdrm.so.2", use_errno=True)
    library.drmOpen.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    library.drmOpen.restype = ctypes.c_int32
    library.drmCommandWriteRead.argtypes = [
        ctypes.c_int32,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    library.drmCommandWriteRead.restype = ctypes.c_int32
    bus_id = f"pci:{address[0]:04x}:{address[1]:02x}:{address[2]:02x}.{address[3]}".encode("ascii")
    descriptor = library.drmOpen(b"radeon", bus_id)
    if descriptor < 0:
        native_errno = ctypes.get_errno()
        if native_errno in (errno.EACCES, errno.EPERM):
            raise PermissionError("Radeon memory access requires DRM device permission.")
        raise StateError(
            "Radeon DRM device could not be opened.", details={"native_errno": native_errno}
        )
    try:
        actual_device = os.fstat(descriptor).st_rdev
        if (os.major(actual_device), os.minor(actual_device)) != device_number:
            raise ValidationError("Radeon native descriptor contradicts the physical DRM node.")
        result = RadeonGemInfo()
        if ctypes.sizeof(result) != 24:
            raise ValidationError("Radeon GEM capacity ABI is invalid.")
        status = library.drmCommandWriteRead(
            descriptor, 0x1C, ctypes.byref(result), ctypes.sizeof(result)
        )
        if status in (-errno.EACCES, -errno.EPERM):
            raise PermissionError("Radeon memory query requires DRM device permission.")
        if status != 0:
            raise StateError(
                "Radeon native capacity query failed.", details={"native_status": status}
            )
        if result.visible_vram_bytes > result.vram_bytes or result.vram_bytes >= 2**63:
            raise ValidationError("Radeon native memory capacities conflict.")
        return result.vram_bytes or None
    finally:
        os.close(descriptor)
