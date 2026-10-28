"""SoAI - SoAIBench OpenCL device metadata [backend/hardware/soaibench/opencl_device_info.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field

from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_bindings import (
    CL_DEVICE_TYPE_GPU,
    CL_DEVICE_UUID_KHR,
    OpenCLBindings,
    check_opencl_result,
    query_opencl_device_scalar,
)

__all__ = (
    "OpenCLDeviceCapabilities",
    "OpenCLDeviceInfo",
    "OpenCLGpuDevice",
    "MAX_OPENCL_INFO_STRING_BYTES",
    "read_opencl_platform_string",
    "read_opencl_device_string",
    "read_opencl_device_ulong",
    "read_opencl_device_uint",
    "read_optional_opencl_device_uuid",
)

MAX_OPENCL_INFO_STRING_BYTES = 4096


@dataclass(frozen=True, slots=True)
class OpenCLDeviceCapabilities:
    device_type: int = CL_DEVICE_TYPE_GPU
    profile: str | None = None
    available: bool | None = None
    compiler_available: bool | None = None
    execution_capabilities: int | None = None


@dataclass(frozen=True, slots=True)
class OpenCLDeviceInfo:
    platform_name: str
    platform_vendor: str
    device_name: str
    device_vendor: str
    driver_version: str
    global_mem_bytes: int
    max_alloc_bytes: int
    capabilities: OpenCLDeviceCapabilities = field(
        default_factory=OpenCLDeviceCapabilities, kw_only=True
    )
    custom_discovery_warning: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True, slots=True)
class OpenCLGpuDevice(OpenCLDeviceInfo):
    platform_handle: int
    device_handle: int
    device_uuid: str | None
    pci_bdf: str | None
    ordinal: int
    platform_device_index: int = 0
    device_version: str = ""
    enumeration_warnings: tuple[str, ...] = ()
    platform_version: str = ""


def read_opencl_platform_string(
    bindings: OpenCLBindings, platform_handle: int, information_field: int
) -> str:
    return _info_string(
        bindings,
        ctypes.c_void_p(platform_handle),
        information_field,
        is_platform=True,
    )


def read_opencl_device_string(
    bindings: OpenCLBindings, device_handle: int, information_field: int
) -> str:
    return _info_string(
        bindings,
        ctypes.c_void_p(device_handle),
        information_field,
        is_platform=False,
    )


def read_optional_opencl_device_uuid(bindings: OpenCLBindings, device_handle: int) -> str | None:
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


def read_opencl_device_ulong(
    bindings: OpenCLBindings, device_handle: int, information_field: int
) -> int:
    value = ctypes.c_ulonglong(0)
    code, result = query_opencl_device_scalar(bindings, device_handle, information_field, value)
    check_opencl_result(code, "opencl_runtime_error", "OpenCL device memory query failed.")
    return result


def read_opencl_device_uint(
    bindings: OpenCLBindings, device_handle: int, information_field: int
) -> int:
    code, result = query_opencl_device_scalar(
        bindings, device_handle, information_field, ctypes.c_uint(0)
    )
    check_opencl_result(code, "opencl_runtime_error", "OpenCL device capability query failed.")
    return result


def _info_string(
    bindings: OpenCLBindings,
    handle: ctypes.c_void_p,
    information_field: int,
    *,
    is_platform: bool,
) -> str:
    size = ctypes.c_size_t(0)
    function = (
        bindings.library.clGetPlatformInfo if is_platform else bindings.library.clGetDeviceInfo
    )
    code = function(handle, information_field, 0, None, ctypes.byref(size))
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL info size query failed.")
    if size.value < 1:
        return ""
    if size.value > MAX_OPENCL_INFO_STRING_BYTES:
        raise SoAIBenchUnsupported(
            reason="opencl_runtime_error",
            message="OpenCL returned an oversized device or platform identifier.",
        )
    buffer = ctypes.create_string_buffer(size.value)
    code = function(handle, information_field, size, buffer, None)
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL info query failed.")
    return buffer.value.decode("utf-8", errors="replace").strip()
