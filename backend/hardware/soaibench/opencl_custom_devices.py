"""SoAI - Physically verified Custom OpenCL GPU discovery [backend/hardware/soaibench/opencl_custom_devices.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import replace

from core.hardware.gpu_identity_normalization import normalize_identity_name
from hardware.soaibench.device_matching import opencl_vendor_matches
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_bindings import (
    CL_DEVICE_AVAILABLE,
    CL_DEVICE_COMPILER_AVAILABLE,
    CL_DEVICE_DRIVER_VERSION,
    CL_DEVICE_EXECUTION_CAPABILITIES,
    CL_DEVICE_GLOBAL_MEM_SIZE,
    CL_DEVICE_MAX_MEM_ALLOC_SIZE,
    CL_DEVICE_NAME,
    CL_DEVICE_NOT_FOUND,
    CL_DEVICE_PROFILE,
    CL_DEVICE_TYPE,
    CL_DEVICE_TYPE_CUSTOM,
    CL_DEVICE_VENDOR,
    CL_DEVICE_VERSION,
    CL_EXEC_KERNEL,
    CL_INVALID_DEVICE_TYPE,
    CL_PLATFORM_NAME,
    CL_PLATFORM_VENDOR,
    CL_PLATFORM_VERSION,
    OpenCLBindings,
    OpenCLUnsignedLong,
    check_opencl_result,
)
from hardware.soaibench.opencl_device_info import (
    OpenCLDeviceCapabilities,
    OpenCLGpuDevice,
    read_opencl_device_string,
    read_opencl_device_uint,
    read_opencl_device_ulong,
    read_opencl_platform_string,
    read_optional_opencl_device_uuid,
)
from hardware.soaibench.opencl_pci_identity import (
    OpenCLPCIIdentityConflict,
    optional_opencl_device_pci_bdf,
)
from hardware.soaibench.opencl_physical_identity import (
    has_strong_opencl_identity,
    opencl_pci_evidence_conflicts,
    opencl_uuid_evidence_conflicts,
)
from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = ("enumerate_physical_custom_gpus",)

MAX_CUSTOM_DEVICES_PER_PLATFORM = 256


def enumerate_physical_custom_gpus(
    bindings: OpenCLBindings,
    platforms: list[int],
    identity: SoAIBenchGpuIdentity,
    ordinal_offset: int,
) -> list[OpenCLGpuDevice]:
    devices: list[OpenCLGpuDevice] = []
    failures: list[SoAIBenchUnsupported] = []
    for platform_handle in platforms:
        try:
            handles = _custom_handles(bindings, platform_handle)
        except SoAIBenchUnsupported as exception:
            failures.append(exception)
            continue
        for platform_device_index, device_handle in enumerate(handles):
            try:
                device = _physical_custom_device(
                    bindings,
                    platform_handle,
                    device_handle,
                    identity,
                    ordinal_offset + len(devices),
                    platform_device_index,
                )
            except SoAIBenchUnsupported as exception:
                if exception.reason in (
                    "opencl_device_identity_conflict",
                    "opencl_custom_identity_unproved",
                ):
                    raise
                failures.append(exception)
                continue
            if device is not None:
                devices.append(device)
    if failures:
        if not devices:
            raise failures[0]
        warning = "; ".join(f"{failure.reason}: {failure.message}" for failure in failures[:32])
        devices = [replace(device, custom_discovery_warning=warning) for device in devices]
    return devices


def _physical_custom_device(
    bindings: OpenCLBindings,
    platform_handle: int,
    device_handle: int,
    identity: SoAIBenchGpuIdentity,
    ordinal: int,
    platform_device_index: int,
) -> OpenCLGpuDevice | None:
    if read_opencl_device_ulong(bindings, device_handle, CL_DEVICE_TYPE) != CL_DEVICE_TYPE_CUSTOM:
        return None
    device_uuid = read_optional_opencl_device_uuid(bindings, device_handle)
    if device_uuid == "0" * 32:
        device_uuid = None
    try:
        pci_bdf = optional_opencl_device_pci_bdf(bindings, device_handle)
    except OpenCLPCIIdentityConflict as exception:
        if exception.concerns_selected_gpu(identity, device_uuid):
            raise
        return None
    if not has_strong_opencl_identity(identity, device_uuid, pci_bdf):
        return None
    if opencl_uuid_evidence_conflicts(
        identity.gpu_uuid, device_uuid
    ) or opencl_pci_evidence_conflicts(identity.pci_bdf, pci_bdf):
        raise SoAIBenchUnsupported(
            reason="opencl_device_identity_conflict",
            message="OpenCL physical identity conflicts with the selected GPU.",
        )
    device = _custom_device(
        bindings,
        platform_handle,
        device_handle,
        device_uuid,
        pci_bdf,
        ordinal,
        platform_device_index,
    )
    _require_custom_gpu_capabilities(identity, device)
    return device


def _custom_handles(bindings: OpenCLBindings, platform_handle: int) -> list[int]:
    count = ctypes.c_uint(0)
    code = bindings.library.clGetDeviceIDs(
        ctypes.c_void_p(platform_handle),
        OpenCLUnsignedLong(CL_DEVICE_TYPE_CUSTOM),
        0,
        None,
        ctypes.byref(count),
    )
    if int(code) in (CL_DEVICE_NOT_FOUND, CL_INVALID_DEVICE_TYPE):
        return []
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL Custom device count failed.")
    if count.value == 0:
        return []
    if count.value > MAX_CUSTOM_DEVICES_PER_PLATFORM:
        raise SoAIBenchUnsupported(
            reason="opencl_runtime_error",
            message="OpenCL exposed too many Custom devices to inspect safely.",
        )
    handles = (ctypes.c_void_p * count.value)()
    code = bindings.library.clGetDeviceIDs(
        ctypes.c_void_p(platform_handle),
        OpenCLUnsignedLong(CL_DEVICE_TYPE_CUSTOM),
        count,
        handles,
        None,
    )
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL Custom device listing failed.")
    return [int(handle) for handle in handles if handle]


def _custom_device(
    bindings: OpenCLBindings,
    platform_handle: int,
    device_handle: int,
    device_uuid: str | None,
    pci_bdf: str | None,
    ordinal: int,
    platform_device_index: int,
) -> OpenCLGpuDevice:
    return OpenCLGpuDevice(
        platform_handle=platform_handle,
        device_handle=device_handle,
        platform_name=read_opencl_platform_string(bindings, platform_handle, CL_PLATFORM_NAME),
        platform_vendor=read_opencl_platform_string(bindings, platform_handle, CL_PLATFORM_VENDOR),
        platform_version=read_opencl_platform_string(
            bindings, platform_handle, CL_PLATFORM_VERSION
        ),
        device_name=read_opencl_device_string(bindings, device_handle, CL_DEVICE_NAME),
        device_vendor=read_opencl_device_string(bindings, device_handle, CL_DEVICE_VENDOR),
        device_version=read_opencl_device_string(bindings, device_handle, CL_DEVICE_VERSION),
        driver_version=read_opencl_device_string(bindings, device_handle, CL_DEVICE_DRIVER_VERSION),
        global_mem_bytes=read_opencl_device_ulong(
            bindings, device_handle, CL_DEVICE_GLOBAL_MEM_SIZE
        ),
        max_alloc_bytes=read_opencl_device_ulong(
            bindings, device_handle, CL_DEVICE_MAX_MEM_ALLOC_SIZE
        ),
        device_uuid=device_uuid,
        pci_bdf=pci_bdf,
        ordinal=ordinal,
        platform_device_index=platform_device_index,
        capabilities=OpenCLDeviceCapabilities(
            device_type=CL_DEVICE_TYPE_CUSTOM,
            profile=read_opencl_device_string(bindings, device_handle, CL_DEVICE_PROFILE),
            available=bool(read_opencl_device_uint(bindings, device_handle, CL_DEVICE_AVAILABLE)),
            compiler_available=bool(
                read_opencl_device_uint(bindings, device_handle, CL_DEVICE_COMPILER_AVAILABLE)
            ),
            execution_capabilities=read_opencl_device_ulong(
                bindings, device_handle, CL_DEVICE_EXECUTION_CAPABILITIES
            ),
        ),
    )


def _require_custom_gpu_capabilities(
    identity: SoAIBenchGpuIdentity, device: OpenCLGpuDevice
) -> None:
    vendor = identity.raw_vendor or identity.vendor
    if normalize_identity_name(vendor or "") in {"", "unknown"} or not opencl_vendor_matches(
        vendor, device.device_vendor, ""
    ):
        raise SoAIBenchUnsupported(
            reason="opencl_custom_identity_unproved",
            message="OpenCL did not provide consistent physical GPU vendor evidence.",
        )
    if not device.capabilities.available:
        raise SoAIBenchUnsupported(
            reason="opencl_device_lost",
            message="The selected OpenCL device is currently unavailable.",
        )
    if not device.capabilities.compiler_available:
        raise SoAIBenchUnsupported(
            reason="opencl_compiler_unavailable",
            message="The selected OpenCL runtime cannot compile benchmark kernels.",
        )
    if not (device.capabilities.execution_capabilities or 0) & CL_EXEC_KERNEL:
        raise SoAIBenchUnsupported(
            reason="opencl_kernel_execution_unavailable",
            message="The selected OpenCL runtime cannot execute source-compiled kernels.",
        )
    if not device.device_name or not 0 < device.max_alloc_bytes <= device.global_mem_bytes:
        raise SoAIBenchUnsupported(
            reason="opencl_runtime_error",
            message="OpenCL returned invalid GPU device information.",
        )
