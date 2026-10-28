"""SoAI - SoAIBench OpenCL GPU enumeration [backend/hardware/soaibench/opencl_devices.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import replace

from hardware.soaibench.device_matching import match_opencl_device
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_bindings import (
    CL_DEVICE_DRIVER_VERSION,
    CL_DEVICE_GLOBAL_MEM_SIZE,
    CL_DEVICE_MAX_MEM_ALLOC_SIZE,
    CL_DEVICE_NAME,
    CL_DEVICE_NOT_FOUND,
    CL_DEVICE_TYPE,
    CL_DEVICE_TYPE_GPU,
    CL_DEVICE_VENDOR,
    CL_DEVICE_VERSION,
    CL_PLATFORM_NAME,
    CL_PLATFORM_VENDOR,
    CL_PLATFORM_VERSION,
    OpenCLBindings,
    OpenCLUnsignedLong,
    check_opencl_result,
)
from hardware.soaibench.opencl_custom_devices import enumerate_physical_custom_gpus
from hardware.soaibench.opencl_device_info import (
    OpenCLDeviceCapabilities,
    OpenCLGpuDevice,
    read_opencl_device_string,
    read_opencl_device_ulong,
    read_opencl_platform_string,
    read_optional_opencl_device_uuid,
)
from hardware.soaibench.opencl_loader import load_opencl_library
from hardware.soaibench.opencl_pci_identity import (
    OpenCLPCIIdentityConflict,
    optional_opencl_device_pci_bdf,
)
from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = (
    "enumerate_opencl_gpu_devices_for_bindings",
    "enumerate_opencl_gpu_devices",
)

MAX_OPENCL_PLATFORMS = 256
MAX_OPENCL_GPU_DEVICES_PER_PLATFORM = 256
MAX_ENUMERATION_WARNINGS = 32


def enumerate_opencl_gpu_devices(
    identity: SoAIBenchGpuIdentity | None = None,
) -> list[OpenCLGpuDevice]:
    bindings = OpenCLBindings(load_opencl_library())
    return enumerate_opencl_gpu_devices_for_bindings(bindings, identity)


def enumerate_opencl_gpu_devices_for_bindings(
    bindings: OpenCLBindings,
    identity: SoAIBenchGpuIdentity | None = None,
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
        platform_version = _optional_platform_string(
            bindings, platform_handle, CL_PLATFORM_VERSION, warnings, platform_index
        )
        for platform_device_index, device_handle in enumerate(platform_devices):
            device_uuid = None
            try:
                if not _is_gpu(bindings, device_handle):
                    continue
                device_uuid = read_optional_opencl_device_uuid(bindings, device_handle)
                device_name = read_opencl_device_string(bindings, device_handle, CL_DEVICE_NAME)
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
                        platform_version=platform_version,
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
                        global_mem_bytes=read_opencl_device_ulong(
                            bindings,
                            device_handle,
                            CL_DEVICE_GLOBAL_MEM_SIZE,
                        ),
                        max_alloc_bytes=read_opencl_device_ulong(
                            bindings,
                            device_handle,
                            CL_DEVICE_MAX_MEM_ALLOC_SIZE,
                        ),
                        device_uuid=device_uuid,
                        pci_bdf=optional_opencl_device_pci_bdf(bindings, device_handle),
                        ordinal=len(devices),
                        platform_device_index=platform_device_index,
                        capabilities=OpenCLDeviceCapabilities(
                            device_type=read_opencl_device_ulong(
                                bindings, device_handle, CL_DEVICE_TYPE
                            )
                        ),
                    )
                )
            except OpenCLPCIIdentityConflict as exception:
                if identity is None or exception.concerns_selected_gpu(identity, device_uuid):
                    raise
                _record_enumeration_warning(
                    warnings,
                    f"platform_{platform_index}_device_{platform_device_index}:identity_conflict",
                )
            except SoAIBenchUnsupported as exception:
                if exception.reason == "opencl_device_identity_conflict":
                    raise
                _record_enumeration_warning(
                    warnings,
                    f"platform_{platform_index}_device_{platform_device_index}:required_info_unavailable",
                )
    if identity is not None:
        try:
            devices.extend(
                enumerate_physical_custom_gpus(bindings, platforms, identity, len(devices))
            )
        except SoAIBenchUnsupported as custom_failure:
            if custom_failure.reason in (
                "opencl_device_identity_conflict",
                "opencl_custom_identity_unproved",
            ):
                raise
            if not devices:
                raise
            try:
                match_opencl_device(identity, devices)
            except SoAIBenchUnsupported as match_failure:
                raise custom_failure from match_failure
            devices = [
                replace(
                    device,
                    custom_discovery_warning=f"{custom_failure.reason}: {custom_failure.message}",
                )
                for device in devices
            ]
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
        return read_opencl_platform_string(bindings, platform_handle, field)
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
        return read_opencl_device_string(bindings, device_handle, field)
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
            message="OpenCL exposed more platforms than SoAI Bench can inspect safely.",
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
            message="OpenCL exposed more GPU devices than SoAI Bench can inspect safely.",
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
