"""SoAI - SoAIBench OpenCL PCI identity extraction [backend/hardware/soaibench/opencl_pci_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import sys
from typing import TYPE_CHECKING

from core.hardware.gpu_identity_normalization import observed_pci_bdf_conflicts
from hardware.soaibench.errors import SoAIBenchUnsupported
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
from hardware.soaibench.opencl_physical_identity import (
    comparable_opencl_uuid,
    matching_opencl_pci_bdf,
    matching_opencl_uuid,
)

if TYPE_CHECKING:
    from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = ("OpenCLPCIIdentityConflict", "optional_opencl_device_pci_bdf")

AMD_TOPOLOGY_BYTE_SIZE = 24
AMD_TOPOLOGY_BUS_OFFSET = 21
AMD_TOPOLOGY_DEVICE_OFFSET = 22
AMD_TOPOLOGY_FUNCTION_OFFSET = 23


class OpenCLPCIIdentityConflict(SoAIBenchUnsupported):
    observations: tuple[str, ...]

    def __init__(self, observations: tuple[str, ...]) -> None:
        super().__init__(
            reason="opencl_device_identity_conflict",
            message="OpenCL PCI identity sources disagree for the selected device.",
            diagnostic=", ".join(observations),
        )
        self.observations = observations

    def concerns_selected_gpu(
        self, identity: SoAIBenchGpuIdentity, device_uuid: str | None
    ) -> bool:
        if matching_opencl_uuid(identity.gpu_uuid, device_uuid) or any(
            matching_opencl_pci_bdf(identity.pci_bdf, address) for address in self.observations
        ):
            return True
        distinct_uuids = (
            comparable_opencl_uuid(identity.gpu_uuid or "") is not None
            and comparable_opencl_uuid(device_uuid or "") is not None
        )
        return not distinct_uuids and not matching_opencl_pci_bdf(
            identity.pci_bdf, identity.pci_bdf
        )


def optional_opencl_device_pci_bdf(bindings: OpenCLBindings, device_handle: int) -> str | None:
    observations = [
        address
        for address in (
            _optional_khr_pci_bdf(bindings, device_handle),
            _optional_amd_pci_bdf(bindings, device_handle),
            _optional_nvidia_pci_bdf(bindings, device_handle),
        )
        if address is not None
    ]
    if any(
        observed_pci_bdf_conflicts(first, second)
        for position, first in enumerate(observations)
        for second in observations[position + 1 :]
    ):
        raise OpenCLPCIIdentityConflict(tuple(observations))
    return observations[0] if observations else None


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
    domain_text = f"{domain:04x}" if domain <= 0xFFFF else f"{domain:08x}"
    return f"{domain_text}:{bus:02x}:{device:02x}.{function}"
