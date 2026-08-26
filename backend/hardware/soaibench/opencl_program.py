"""SoAI - SoAIBench OpenCL program helpers [backend/hardware/soaibench/opencl_program.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable

from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_bindings import (
    CL_MEM_READ_WRITE,
    CL_PROGRAM_BUILD_LOG,
    CL_TRUE,
    check_opencl_result,
)
from hardware.soaibench.opencl_runtime import OpenCLRuntime

__all__ = (
    "create_buffer",
    "create_kernel",
    "create_program",
    "enqueue_kernel",
    "finish_queue",
    "read_float_buffer",
    "release_buffer",
    "release_kernel",
    "release_program",
    "set_buffer_arg",
    "set_uint_arg",
)


def create_program(runtime: OpenCLRuntime, source: str) -> int:
    source_bytes = source.encode("utf-8")
    source_array = (ctypes.c_char_p * 1)(ctypes.c_char_p(source_bytes))
    source_size = (ctypes.c_size_t * 1)(len(source_bytes))
    error_code = ctypes.c_int(0)
    program = runtime.bindings.library.clCreateProgramWithSource(
        ctypes.c_void_p(runtime.context),
        1,
        source_array,
        source_size,
        ctypes.byref(error_code),
    )
    check_opencl_result(
        int(error_code.value),
        "opencl_runtime_error",
        "OpenCL program creation failed.",
    )
    if not program:
        raise SoAIBenchUnsupported(
            reason="opencl_runtime_error",
            message="OpenCL returned an empty program handle.",
        )
    code = runtime.bindings.library.clBuildProgram(
        ctypes.c_void_p(int(program)),
        1,
        (ctypes.c_void_p * 1)(ctypes.c_void_p(runtime.device)),
        None,
        None,
        None,
    )
    if int(code) != 0:
        _raise_program_build_failed(runtime, int(program), int(code))
    return int(program)


def create_kernel(runtime: OpenCLRuntime, program: int, name: str) -> int:
    error_code = ctypes.c_int(0)
    kernel = runtime.bindings.library.clCreateKernel(
        ctypes.c_void_p(program),
        name.encode("utf-8"),
        ctypes.byref(error_code),
    )
    check_opencl_result(
        int(error_code.value),
        "opencl_kernel_compile_failed",
        "OpenCL kernel creation failed.",
    )
    if not kernel:
        raise SoAIBenchUnsupported(
            reason="opencl_kernel_compile_failed",
            message="OpenCL returned an empty kernel handle.",
        )
    return int(kernel)


def create_buffer(
    runtime: OpenCLRuntime,
    size_bytes: int,
) -> int:
    error_code = ctypes.c_int(0)
    buffer = runtime.bindings.library.clCreateBuffer(
        ctypes.c_void_p(runtime.context),
        CL_MEM_READ_WRITE,
        ctypes.c_size_t(size_bytes),
        None,
        ctypes.byref(error_code),
    )
    check_opencl_result(
        int(error_code.value),
        "opencl_runtime_error",
        "OpenCL buffer creation failed.",
    )
    if not buffer:
        raise SoAIBenchUnsupported(
            reason="opencl_runtime_error",
            message="OpenCL returned an empty buffer handle.",
        )
    return int(buffer)


def set_buffer_arg(runtime: OpenCLRuntime, kernel: int, index: int, buffer: int) -> None:
    value = ctypes.c_void_p(buffer)
    code = runtime.bindings.library.clSetKernelArg(
        ctypes.c_void_p(kernel),
        ctypes.c_uint(index),
        ctypes.sizeof(value),
        ctypes.byref(value),
    )
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL buffer arg failed.")


def set_uint_arg(runtime: OpenCLRuntime, kernel: int, index: int, value: int) -> None:
    arg = ctypes.c_uint(value)
    code = runtime.bindings.library.clSetKernelArg(
        ctypes.c_void_p(kernel),
        ctypes.c_uint(index),
        ctypes.sizeof(arg),
        ctypes.byref(arg),
    )
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL uint arg failed.")


def enqueue_kernel(runtime: OpenCLRuntime, kernel: int, global_size_value: int) -> None:
    global_size = (ctypes.c_size_t * 1)(global_size_value)
    code = runtime.bindings.library.clEnqueueNDRangeKernel(
        ctypes.c_void_p(runtime.queue),
        ctypes.c_void_p(kernel),
        1,
        None,
        global_size,
        None,
        0,
        None,
        None,
    )
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL kernel enqueue failed.")


def finish_queue(runtime: OpenCLRuntime) -> None:
    code = runtime.bindings.library.clFinish(ctypes.c_void_p(runtime.queue))
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL queue finish failed.")


def read_float_buffer(runtime: OpenCLRuntime, buffer: int, count: int) -> list[float]:
    data = (ctypes.c_float * count)()
    code = runtime.bindings.library.clEnqueueReadBuffer(
        ctypes.c_void_p(runtime.queue),
        ctypes.c_void_p(buffer),
        CL_TRUE,
        0,
        ctypes.sizeof(data),
        ctypes.c_void_p(ctypes.addressof(data)),
        0,
        None,
        None,
    )
    check_opencl_result(int(code), "opencl_runtime_error", "OpenCL buffer read failed.")
    return [float(value) for value in data]


def release_buffer(runtime: OpenCLRuntime, buffer: int) -> None:
    _release(runtime.bindings.library.clReleaseMemObject, buffer, "OpenCL buffer release failed.")


def release_kernel(runtime: OpenCLRuntime, kernel: int) -> None:
    _release(runtime.bindings.library.clReleaseKernel, kernel, "OpenCL kernel release failed.")


def release_program(runtime: OpenCLRuntime, program: int) -> None:
    _release(runtime.bindings.library.clReleaseProgram, program, "OpenCL program release failed.")


def _raise_program_build_failed(runtime: OpenCLRuntime, program: int, code: int) -> None:
    build_log = ""
    log_exception: SoAIBenchUnsupported | None = None
    try:
        build_log = _program_build_log(runtime, program)
    except SoAIBenchUnsupported as exception:
        log_exception = exception
    build_exception = SoAIBenchUnsupported(
        reason="opencl_kernel_compile_failed",
        message=build_log or f"OpenCL kernel compilation failed with code {code}.",
    )
    if log_exception is not None:
        build_exception.add_note(f"OpenCL build log query failed: {log_exception}")
    try:
        release_program(runtime, program)
    except SoAIBenchUnsupported as cleanup_exception:
        build_exception.add_note(f"OpenCL program cleanup failed: {cleanup_exception}")
    raise build_exception


def _program_build_log(runtime: OpenCLRuntime, program: int) -> str:
    size = ctypes.c_size_t(0)
    code = runtime.bindings.library.clGetProgramBuildInfo(
        ctypes.c_void_p(program),
        ctypes.c_void_p(runtime.device),
        CL_PROGRAM_BUILD_LOG,
        0,
        None,
        ctypes.byref(size),
    )
    check_opencl_result(
        int(code),
        "opencl_kernel_compile_failed",
        "OpenCL program build log size query failed.",
    )
    if size.value < 1:
        return ""
    buffer = ctypes.create_string_buffer(size.value)
    code = runtime.bindings.library.clGetProgramBuildInfo(
        ctypes.c_void_p(program),
        ctypes.c_void_p(runtime.device),
        CL_PROGRAM_BUILD_LOG,
        size,
        buffer,
        None,
    )
    check_opencl_result(
        int(code),
        "opencl_kernel_compile_failed",
        "OpenCL program build log query failed.",
    )
    return buffer.value.decode("utf-8", errors="replace").strip()


def _release(release: Callable[[ctypes.c_void_p], int], handle: int, message: str) -> None:
    code = release(ctypes.c_void_p(handle))
    check_opencl_result(int(code), "opencl_runtime_error", message)
