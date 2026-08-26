"""SoAI - SoAIBench OpenCL PCI identity extraction [backend/hardware/soaibench/opencl_pci_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes

from hardware.soaibench.opencl_bindings import (
    CL_DEVICE_PCI_BUS_ID_NV,
    CL_DEVICE_PCI_BUS_INFO_KHR,
    CL_DEVICE_PCI_SLOT_ID_NV,
    CL_DEVICE_TOPOLOGY_AMD,
    CL_DEVICE_TOPOLOGY_TYPE_PCIE_AMD,
    CL_INVALID_VALUE,
    OpenCLBindings,
)

__all__ = ("optional_opencl_device_pci_bdf",)


def optional_opencl_device_pci_bdf(bindings: OpenCLBindings, device_handle: int) -> str | None:
    return (
        _optional_khr_pci_bdf(bindings, device_handle)
        or _optional_amd_pci_bdf(bindings, device_handle)
        or _optional_nvidia_pci_bdf(bindings, device_handle)
    )


def _optional_khr_pci_bdf(bindings: OpenCLBindings, device_handle: int) -> str | None:
    values = (ctypes.c_uint * 4)()
    code = bindings.library.clGetDeviceInfo(
        ctypes.c_void_p(device_handle),
        CL_DEVICE_PCI_BUS_INFO_KHR,
        ctypes.sizeof(values),
        ctypes.byref(values),
        None,
    )
    if int(code) != 0:
        return None
    domain = int(values[0])
    bus = int(values[1])
    device = int(values[2])
    function = int(values[3])
    return _format_pci_bdf(domain, bus, device, function)


def _optional_amd_pci_bdf(bindings: OpenCLBindings, device_handle: int) -> str | None:
    values = (ctypes.c_uint * 6)()
    code = bindings.library.clGetDeviceInfo(
        ctypes.c_void_p(device_handle),
        CL_DEVICE_TOPOLOGY_AMD,
        ctypes.sizeof(values),
        ctypes.byref(values),
        None,
    )
    if int(code) != 0 or int(values[0]) != CL_DEVICE_TOPOLOGY_TYPE_PCIE_AMD:
        return None
    bus = int(values[2])
    device = int(values[3])
    function = int(values[4])
    return _format_pci_bdf(None, bus, device, function)


def _optional_nvidia_pci_bdf(bindings: OpenCLBindings, device_handle: int) -> str | None:
    bus_id = _optional_device_uint(bindings, device_handle, CL_DEVICE_PCI_BUS_ID_NV)
    slot_id = _optional_device_uint(bindings, device_handle, CL_DEVICE_PCI_SLOT_ID_NV)
    if bus_id is None or slot_id is None:
        return None
    return _format_pci_bdf(None, bus_id, slot_id, 0)


def _optional_device_uint(
    bindings: OpenCLBindings,
    device_handle: int,
    field: int,
) -> int | None:
    value = ctypes.c_uint(0)
    code = bindings.library.clGetDeviceInfo(
        ctypes.c_void_p(device_handle),
        field,
        ctypes.sizeof(value),
        ctypes.byref(value),
        None,
    )
    if int(code) == 0:
        return int(value.value)
    if int(code) == CL_INVALID_VALUE:
        return None
    return None


def _format_pci_bdf(domain: int | None, bus: int, device: int, function: int) -> str:
    if domain is None:
        return f"{bus:02x}:{device:02x}.{function}"
    return f"{domain:04x}:{bus:02x}:{device:02x}.{function}"
