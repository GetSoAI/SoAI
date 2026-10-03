"""SoAI - SoAIBench OpenCL GPU enumeration [backend/hardware/soaibench/opencl_devices.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import dataclass, replace

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
    CL_DEVICE_VERSION,
    CL_PLATFORM_NAME,
    CL_PLATFORM_VENDOR,
    OpenCLBindings,
    OpenCLUnsignedLong,
    check_opencl_result,
    query_opencl_device_scalar,
)
from hardware.soaibench.opencl_device_info import OpenCLDeviceInfo
from hardware.soaibench.opencl_loader import load_opencl_library
from hardware.soaibench.opencl_pci_identity import optional_opencl_device_pci_bdf

__all__ = (
    "OpenCLGpuDevice",
    "enumerate_opencl_gpu_devices",
    "enumerate_opencl_gpu_devices_for_bindings",
)

MAX_OPENCL_PLATFORMS = 256
MAX_OPENCL_GPU_DEVICES_PER_PLATFORM = 256
MAX_ENUMERATION_WARNINGS = 32
MAX_OPENCL_INFO_STRING_BYTES = 4096


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


def enumerate_opencl_gpu_devices() -> list[OpenCLGpuDevice]:
    bindings = OpenCLBindings(load_opencl_library())
    return enumerate_opencl_gpu_devices_for_bindings(bindings)


def enumerate_opencl_gpu_devices_for_bindings(
    bindings: OpenCLBindings,
) -> list[OpenCLGpuDevice]:
    platforms = _platforms(bindings)
    devices: list[OpenCLGpuDevice] = []
    warnings: list[str] = []
    for platform_index, platform_handle in enumerate(platforms):
        try:
            platform_devices = _gpu_devices_for_platform(bindings, platform_handle)
        except SoAIBenchUnsupported:
            _record_enumeration_warning(warnings, f"platform_{platform_index}:gpu_query_failed")
            continue
        platform_name = _optional_platform_string(
            bindings, platform_handle, CL_PLATFORM_NAME, warnings, platform_index
        )
        platform_vendor = _optional_platform_string(
            bindings, platform_handle, CL_PLATFORM_VENDOR, warnings, platform_index
        )
        for platform_device_index, device_handle in enumerate(platform_devices):
            try:
                if not _is_gpu(bindings, device_handle):
                    continue
                device_name = _device_string(bindings, device_handle, CL_DEVICE_NAME)
                if not device_name:
                    raise SoAIBenchUnsupported(
                        reason="opencl_device_name_unavailable",
                        message="OpenCL did not expose a GPU device name.",
                    )
                devices.append(
                    OpenCLGpuDevice(
                        platform_handle=platform_handle,
                        device_handle=device_handle,
                        platform_name=platform_name,
                        platform_vendor=platform_vendor,
                        device_name=device_name,
                        device_vendor=_optional_device_string(
                            bindings,
                            device_handle,
                            CL_DEVICE_VENDOR,
                            warnings,
                            platform_index,
                            platform_device_index,
                        ),
                        device_version=_optional_device_string(
                            bindings,
                            device_handle,
                            CL_DEVICE_VERSION,
                            warnings,
                            platform_index,
                            platform_device_index,
                        ),
                        driver_version=_optional_device_string(
                            bindings,
                            device_handle,
                            CL_DEVICE_DRIVER_VERSION,
                            warnings,
                            platform_index,
                            platform_device_index,
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
                        platform_device_index=platform_device_index,
                    )
                )
            except SoAIBenchUnsupported:
                _record_enumeration_warning(
                    warnings,
                    f"platform_{platform_index}_device_{platform_device_index}:required_info_unavailable",
                )
    if not devices:
        raise SoAIBenchUnsupported(
            reason="opencl_gpu_device_unavailable",
            message="OpenCL did not expose any GPU devices.",
            diagnostic=", ".join(warnings) if warnings else None,
        )
    return [replace(device, enumeration_warnings=tuple(warnings)) for device in devices]


def _record_enumeration_warning(warnings: list[str], warning: str) -> None:
    if len(warnings) < MAX_ENUMERATION_WARNINGS - 1:
        warnings.append(warning)
    elif len(warnings) == MAX_ENUMERATION_WARNINGS - 1:
        warnings.append("additional_opencl_warnings_omitted")


def _optional_platform_string(
    bindings: OpenCLBindings,
    platform_handle: int,
    field: int,
    warnings: list[str],
    platform_index: int,
) -> str:
    try:
        return _platform_string(bindings, platform_handle, field)
    except SoAIBenchUnsupported:
        _record_enumeration_warning(
            warnings, f"platform_{platform_index}_field_{field}:unavailable"
        )
        return ""


def _optional_device_string(
    bindings: OpenCLBindings,
    device_handle: int,
    field: int,
    warnings: list[str],
    platform_index: int,
    device_index: int,
) -> str:
    try:
        return _device_string(bindings, device_handle, field)
    except SoAIBenchUnsupported:
        _record_enumeration_warning(
            warnings, f"platform_{platform_index}_device_{device_index}_field_{field}:unavailable"
        )
        return ""


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
    if count.value > MAX_OPENCL_PLATFORMS:
        raise SoAIBenchUnsupported(
            reason="opencl_platform_unavailable",
            message="OpenCL exposed more platforms than SoAIBench can inspect safely.",
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
    if count.value == 0:
        return []
    if count.value > MAX_OPENCL_GPU_DEVICES_PER_PLATFORM:
        raise SoAIBenchUnsupported(
            reason="opencl_gpu_device_unavailable",
            message="OpenCL exposed more GPU devices than SoAIBench can inspect safely.",
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
    return [int(handle) for handle in device_array if handle]


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
    code, result = query_opencl_device_scalar(bindings, device_handle, field, value)
    check_opencl_result(code, "opencl_runtime_error", "OpenCL device memory query failed.")
    return result


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
    if size.value > MAX_OPENCL_INFO_STRING_BYTES:
        raise SoAIBenchUnsupported(
            reason="opencl_runtime_error",
            message="OpenCL returned an oversized device or platform identifier.",
        )
    buffer = ctypes.create_string_buffer(size.value)
    code = function(handle, field, size, buffer, None)
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL info query failed.")
    return buffer.value.decode("utf-8", errors="replace").strip()
