"""SoAI - SoAIBench OpenCL PCI identity extraction [backend/hardware/soaibench/opencl_pci_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import sys

from hardware.soaibench.opencl_bindings import (
    CL_DEVICE_PCI_BUS_ID_NV,
    CL_DEVICE_PCI_BUS_INFO_KHR,
    CL_DEVICE_PCI_SLOT_ID_NV,
    CL_DEVICE_TOPOLOGY_AMD,
    CL_DEVICE_TOPOLOGY_TYPE_PCIE_AMD,
    CL_INVALID_VALUE,
    OpenCLBindings,
    query_opencl_device_scalar,
)

__all__ = ("optional_opencl_device_pci_bdf",)

AMD_TOPOLOGY_BYTE_SIZE = 24
AMD_TOPOLOGY_BUS_OFFSET = 21
AMD_TOPOLOGY_DEVICE_OFFSET = 22
AMD_TOPOLOGY_FUNCTION_OFFSET = 23


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
    topology = (ctypes.c_ubyte * AMD_TOPOLOGY_BYTE_SIZE)()
    code = bindings.library.clGetDeviceInfo(
        ctypes.c_void_p(device_handle),
        CL_DEVICE_TOPOLOGY_AMD,
        ctypes.sizeof(topology),
        ctypes.byref(topology),
        None,
    )
    topology_type = int.from_bytes(topology[:4], byteorder=sys.byteorder)
    if int(code) != 0 or topology_type != CL_DEVICE_TOPOLOGY_TYPE_PCIE_AMD:
        return None
    return _format_pci_bdf(
        None,
        int(topology[AMD_TOPOLOGY_BUS_OFFSET]),
        int(topology[AMD_TOPOLOGY_DEVICE_OFFSET]),
        int(topology[AMD_TOPOLOGY_FUNCTION_OFFSET]),
    )


def _optional_nvidia_pci_bdf(bindings: OpenCLBindings, device_handle: int) -> str | None:
    bus_id = _optional_device_uint(bindings, device_handle, CL_DEVICE_PCI_BUS_ID_NV)
    slot_id = _optional_device_uint(bindings, device_handle, CL_DEVICE_PCI_SLOT_ID_NV)
    if bus_id is None or slot_id is None:
        return None
    return _format_pci_bdf(None, bus_id & 0xFF, slot_id >> 3, slot_id & 0x7)


def _optional_device_uint(
    bindings: OpenCLBindings,
    device_handle: int,
    field: int,
) -> int | None:
    value = ctypes.c_uint(0)
    code, result = query_opencl_device_scalar(bindings, device_handle, field, value)
    if code == 0:
        return result
    if code == CL_INVALID_VALUE:
        return None
    return None


def _format_pci_bdf(domain: int | None, bus: int, device: int, function: int) -> str:
    if domain is None:
        return f"{bus:02x}:{device:02x}.{function}"
    return f"{domain:04x}:{bus:02x}:{device:02x}.{function}"
