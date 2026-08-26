"""SoAI - SoAIBench OpenCL resource lifecycle [backend/hardware/soaibench/opencl_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass

from hardware.soaibench.device_matching import match_opencl_device
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_bindings import OpenCLBindings, check_opencl_result
from hardware.soaibench.opencl_device_info import OpenCLDeviceInfo
from hardware.soaibench.opencl_devices import enumerate_opencl_gpu_devices_for_bindings
from hardware.soaibench.opencl_loader import load_opencl_library
from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = (
    "OpenCLRuntime",
    "build_opencl_runtime",
    "release_opencl_runtime",
)


@dataclass(frozen=True, slots=True)
class OpenCLRuntime(OpenCLDeviceInfo):
    bindings: OpenCLBindings
    context: int
    queue: int
    device: int
    queue_api: str
    match_basis: str


def build_opencl_runtime(identity: SoAIBenchGpuIdentity) -> OpenCLRuntime:
    bindings = OpenCLBindings(load_opencl_library())
    match = match_opencl_device(identity, enumerate_opencl_gpu_devices_for_bindings(bindings))
    device_array = (ctypes.c_void_p * 1)(ctypes.c_void_p(match.device.device_handle))
    error_code = ctypes.c_int(0)
    context = bindings.library.clCreateContext(
        None,
        1,
        device_array,
        None,
        None,
        ctypes.byref(error_code),
    )
    check_opencl_result(
        int(error_code.value),
        "opencl_context_create_failed",
        "OpenCL context creation failed.",
    )
    if not context:
        raise SoAIBenchUnsupported(
            reason="opencl_context_create_failed",
            message="OpenCL returned an empty context handle.",
        )
    try:
        queue, queue_api = _create_queue(bindings, int(context), match.device.device_handle)
    except SoAIBenchUnsupported as exception:
        _release_context_after_queue_failure(bindings, int(context), exception)
        raise
    return OpenCLRuntime(
        bindings=bindings,
        context=int(context),
        queue=queue,
        device=match.device.device_handle,
        queue_api=queue_api,
        match_basis=match.match_basis,
        platform_name=match.device.platform_name,
        platform_vendor=match.device.platform_vendor,
        device_name=match.device.device_name,
        device_vendor=match.device.device_vendor,
        driver_version=match.device.driver_version,
        global_mem_bytes=match.device.global_mem_bytes,
        max_alloc_bytes=match.device.max_alloc_bytes,
    )


def release_opencl_runtime(runtime: OpenCLRuntime) -> None:
    first_failure: SoAIBenchUnsupported | None = None
    for release, handle, message in (
        (
            runtime.bindings.library.clReleaseCommandQueue,
            runtime.queue,
            "OpenCL command queue release failed.",
        ),
        (
            runtime.bindings.library.clReleaseContext,
            runtime.context,
            "OpenCL context release failed.",
        ),
    ):
        try:
            _release_handle(release, handle, "opencl_runtime_error", message)
        except SoAIBenchUnsupported as exception:
            if first_failure is None:
                first_failure = exception
            else:
                first_failure.add_note(f"Additional OpenCL cleanup failed: {exception}")
    if first_failure is not None:
        raise first_failure


def _create_queue(
    bindings: OpenCLBindings,
    context: int,
    device: int,
) -> tuple[int, str]:
    error_code = ctypes.c_int(0)
    try:
        create_queue_with_properties = bindings.library.clCreateCommandQueueWithProperties
    except AttributeError:
        create_queue_with_properties = None
    if create_queue_with_properties is not None:
        queue = create_queue_with_properties(
            ctypes.c_void_p(context),
            ctypes.c_void_p(device),
            None,
            ctypes.byref(error_code),
        )
        queue_api = "clCreateCommandQueueWithProperties"
    else:
        queue = bindings.library.clCreateCommandQueue(
            ctypes.c_void_p(context),
            ctypes.c_void_p(device),
            0,
            ctypes.byref(error_code),
        )
        queue_api = "clCreateCommandQueue"
    check_opencl_result(
        int(error_code.value),
        "opencl_queue_create_failed",
        "OpenCL command queue creation failed.",
    )
    if not queue:
        raise SoAIBenchUnsupported(
            reason="opencl_queue_create_failed",
            message="OpenCL returned an empty command queue handle.",
        )
    return (int(queue), queue_api)


def _release_handle(
    release: Callable[[ctypes.c_void_p], int],
    handle: int,
    reason: str,
    message: str,
) -> None:
    code = release(ctypes.c_void_p(handle))
    check_opencl_result(int(code), reason, message)


def _release_context_after_queue_failure(
    bindings: OpenCLBindings,
    context: int,
    primary_exception: SoAIBenchUnsupported,
) -> None:
    try:
        _release_handle(
            bindings.library.clReleaseContext,
            context,
            "opencl_context_create_failed",
            "OpenCL context release failed after queue creation failure.",
        )
    except SoAIBenchUnsupported as cleanup_exception:
        primary_exception.add_note(f"OpenCL context cleanup failed: {cleanup_exception}")
