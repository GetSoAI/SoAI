"""SoAI - Non-compute display adapter classification [backend/hardware/gpu_inventory/display_adapters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from hardware.vendors.vendor_metadata import normalize_vendor_value
from hardware.vendors.vendor_types import AMD_VENDOR, INTEL_VENDOR, NVIDIA_VENDOR

__all__ = (
    "BASIC_DISPLAY_DRIVERS",
    "BASIC_DISPLAY_TYPE",
    "BASIC_DISPLAY_VENDOR_IDS",
    "VIRTUAL_DISPLAY_DRIVERS",
    "VIRTUAL_DISPLAY_TYPE",
    "VIRTUAL_DISPLAY_VENDOR_IDS",
    "classify_display_adapter",
)

VIRTUAL_DISPLAY_TYPE = "virtual"
BASIC_DISPLAY_TYPE = "basic"

COMPUTE_GPU_VENDORS: frozenset[str] = frozenset((NVIDIA_VENDOR, AMD_VENDOR, INTEL_VENDOR))

VIRTUAL_DISPLAY_DRIVERS: frozenset[str] = frozenset(
    (
        "bochs-drm",
        "qxl",
        "virtio-pci",
        "virtio_gpu",
        "virtio-gpu",
        "vmwgfx",
        "vboxvideo",
        "hyperv_drm",
        "hyperv_fb",
        "cirrus",
        "simpledrm",
        "simple-framebuffer",
        "vesadrm",
        "vesafb",
        "efifb",
        "offb",
    ),
)

BASIC_DISPLAY_DRIVERS: frozenset[str] = frozenset(("ast", "mgag200"))

VIRTUAL_DISPLAY_VENDOR_IDS: frozenset[str] = frozenset(
    ("1234", "1b36", "1af4", "1013", "15ad", "80ee", "1414"),
)

BASIC_DISPLAY_VENDOR_IDS: frozenset[str] = frozenset(("1a03", "102b"))


def classify_display_adapter(
    vendor: str,
    pci_vendor_id: str,
    kernel_driver: str | None,
) -> str | None:
    if vendor in COMPUTE_GPU_VENDORS:
        return None
    driver = normalize_vendor_value(kernel_driver)
    if driver in VIRTUAL_DISPLAY_DRIVERS:
        return VIRTUAL_DISPLAY_TYPE
    if driver in BASIC_DISPLAY_DRIVERS:
        return BASIC_DISPLAY_TYPE
    vendor_id = normalize_vendor_value(pci_vendor_id)
    if vendor_id in VIRTUAL_DISPLAY_VENDOR_IDS:
        return VIRTUAL_DISPLAY_TYPE
    if vendor_id in BASIC_DISPLAY_VENDOR_IDS:
        return BASIC_DISPLAY_TYPE
    return None
