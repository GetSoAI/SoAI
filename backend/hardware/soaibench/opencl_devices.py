"""SoAI - SoAIBench OpenCL GPU enumeration [backend/hardware/soaibench/opencl_devices.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import dataclass

from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_bindings import (
    CL_DEVICE_DRIVER_VERSION,
    CL_DEVICE_GLOBAL_MEM_SIZE,
    CL_DEVICE_MAX_MEM_ALLOC_SIZE,
    CL_DEVICE_NAME,
    CL_DEVICE_NOT_FOUND,
    CL_DEVICE_TYPE,
    CL_DEVICE_TYPE_GPU,
    CL_DEVICE_UUID_KHR,
    CL_DEVICE_VENDOR,
    CL_PLATFORM_NAME,
    CL_PLATFORM_VENDOR,
    OpenCLBindings,
    OpenCLUnsignedLong,
    check_opencl_result,
)
from hardware.soaibench.opencl_device_info import OpenCLDeviceInfo
from hardware.soaibench.opencl_loader import load_opencl_library
from hardware.soaibench.opencl_pci_identity import optional_opencl_device_pci_bdf

__all__ = (
    "OpenCLGpuDevice",
    "enumerate_opencl_gpu_devices",
    "enumerate_opencl_gpu_devices_for_bindings",
)


@dataclass(frozen=True, slots=True)
class OpenCLGpuDevice(OpenCLDeviceInfo):
    platform_handle: int
    device_handle: int
    device_uuid: str | None
    pci_bdf: str | None
    ordinal: int


def enumerate_opencl_gpu_devices() -> list[OpenCLGpuDevice]:
    bindings = OpenCLBindings(load_opencl_library())
    return enumerate_opencl_gpu_devices_for_bindings(bindings)


def enumerate_opencl_gpu_devices_for_bindings(
    bindings: OpenCLBindings,
) -> list[OpenCLGpuDevice]:
    platforms = _platforms(bindings)
    devices: list[OpenCLGpuDevice] = []
    for platform_handle in platforms:
        platform_devices = _gpu_devices_for_platform(bindings, platform_handle)
        platform_name = _platform_string(bindings, platform_handle, CL_PLATFORM_NAME)
        platform_vendor = _platform_string(bindings, platform_handle, CL_PLATFORM_VENDOR)
        for device_handle in platform_devices:
            devices.append(
                OpenCLGpuDevice(
                    platform_handle=platform_handle,
                    device_handle=device_handle,
                    platform_name=platform_name,
                    platform_vendor=platform_vendor,
                    device_name=_device_string(bindings, device_handle, CL_DEVICE_NAME),
                    device_vendor=_device_string(bindings, device_handle, CL_DEVICE_VENDOR),
                    driver_version=_device_string(
                        bindings,
                        device_handle,
                        CL_DEVICE_DRIVER_VERSION,
                    ),
                    global_mem_bytes=_device_ulong(
                        bindings,
                        device_handle,
                        CL_DEVICE_GLOBAL_MEM_SIZE,
                    ),
                    max_alloc_bytes=_device_ulong(
                        bindings,
                        device_handle,
                        CL_DEVICE_MAX_MEM_ALLOC_SIZE,
                    ),
                    device_uuid=_optional_device_uuid(bindings, device_handle),
                    pci_bdf=optional_opencl_device_pci_bdf(bindings, device_handle),
                    ordinal=len(devices),
                ),
            )
    if not devices:
        raise SoAIBenchUnsupported(
            reason="opencl_gpu_device_unavailable",
            message="OpenCL did not expose any GPU devices.",
        )
    return devices


def _platforms(bindings: OpenCLBindings) -> list[int]:
    count = ctypes.c_uint(0)
    code = bindings.library.clGetPlatformIDs(0, None, ctypes.byref(count))
    check_opencl_result(
        int(code),
        "opencl_platform_unavailable",
        "OpenCL platform enumeration failed.",
    )
    if count.value < 1:
        raise SoAIBenchUnsupported(
            reason="opencl_platform_unavailable",
            message="OpenCL did not expose any platforms.",
        )
    platform_array = (ctypes.c_void_p * count.value)()
    code = bindings.library.clGetPlatformIDs(count, platform_array, None)
    check_opencl_result(
        int(code),
        "opencl_platform_unavailable",
        "OpenCL platform listing failed.",
    )
    return [int(handle) for handle in platform_array if handle]


def _gpu_devices_for_platform(bindings: OpenCLBindings, platform_handle: int) -> list[int]:
    count = ctypes.c_uint(0)
    code = bindings.library.clGetDeviceIDs(
        ctypes.c_void_p(platform_handle),
        OpenCLUnsignedLong(CL_DEVICE_TYPE_GPU),
        0,
        None,
        ctypes.byref(count),
    )
    if int(code) == CL_DEVICE_NOT_FOUND:
        return []
    check_opencl_result(
        int(code),
        "opencl_gpu_device_unavailable",
        "OpenCL GPU device count failed.",
    )
    device_array = (ctypes.c_void_p * count.value)()
    code = bindings.library.clGetDeviceIDs(
        ctypes.c_void_p(platform_handle),
        OpenCLUnsignedLong(CL_DEVICE_TYPE_GPU),
        count,
        device_array,
        None,
    )
    check_opencl_result(
        int(code),
        "opencl_gpu_device_unavailable",
        "OpenCL GPU device listing failed.",
    )
    return [int(handle) for handle in device_array if handle and _is_gpu(bindings, int(handle))]


def _is_gpu(bindings: OpenCLBindings, device_handle: int) -> bool:
    device_type = OpenCLUnsignedLong(0)
    code = bindings.library.clGetDeviceInfo(
        ctypes.c_void_p(device_handle),
        CL_DEVICE_TYPE,
        ctypes.sizeof(device_type),
        ctypes.byref(device_type),
        None,
    )
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL device type query failed.")
    return bool(device_type.value & CL_DEVICE_TYPE_GPU)


def _platform_string(bindings: OpenCLBindings, platform_handle: int, field: int) -> str:
    return _info_string(
        bindings,
        ctypes.c_void_p(platform_handle),
        field,
        is_platform=True,
    )


def _device_string(bindings: OpenCLBindings, device_handle: int, field: int) -> str:
    return _info_string(
        bindings,
        ctypes.c_void_p(device_handle),
        field,
        is_platform=False,
    )


def _optional_device_uuid(bindings: OpenCLBindings, device_handle: int) -> str | None:
    value = (ctypes.c_ubyte * 16)()
    code = bindings.library.clGetDeviceInfo(
        ctypes.c_void_p(device_handle),
        CL_DEVICE_UUID_KHR,
        ctypes.sizeof(value),
        ctypes.byref(value),
        None,
    )
    if int(code) != 0:
        return None
    return "".join(f"{part:02x}" for part in value)


def _device_ulong(bindings: OpenCLBindings, device_handle: int, field: int) -> int:
    value = ctypes.c_ulonglong(0)
    code = bindings.library.clGetDeviceInfo(
        ctypes.c_void_p(device_handle),
        field,
        ctypes.sizeof(value),
        ctypes.byref(value),
        None,
    )
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL device memory query failed.")
    return int(value.value)


def _info_string(
    bindings: OpenCLBindings,
    handle: ctypes.c_void_p,
    field: int,
    *,
    is_platform: bool,
) -> str:
    size = ctypes.c_size_t(0)
    function = (
        bindings.library.clGetPlatformInfo if is_platform else bindings.library.clGetDeviceInfo
    )
    code = function(handle, field, 0, None, ctypes.byref(size))
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL info size query failed.")
    if size.value < 1:
        return ""
    buffer = ctypes.create_string_buffer(size.value)
    code = function(handle, field, size, buffer, None)
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL info query failed.")
    return buffer.value.decode("utf-8", errors="replace").strip()
