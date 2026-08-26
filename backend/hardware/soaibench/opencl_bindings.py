"""SoAI - SoAIBench OpenCL ctypes bindings [backend/hardware/soaibench/opencl_bindings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import dataclass

from hardware.soaibench.errors import SoAIBenchUnsupported

__all__ = (
    "CL_DEVICE_DRIVER_VERSION",
    "CL_DEVICE_GLOBAL_MEM_SIZE",
    "CL_DEVICE_MAX_MEM_ALLOC_SIZE",
    "CL_DEVICE_NAME",
    "CL_DEVICE_PCI_BUS_INFO_KHR",
    "CL_DEVICE_NOT_FOUND",
    "CL_DEVICE_PCI_BUS_ID_NV",
    "CL_DEVICE_PCI_SLOT_ID_NV",
    "CL_DEVICE_TOPOLOGY_AMD",
    "CL_DEVICE_TOPOLOGY_TYPE_PCIE_AMD",
    "CL_DEVICE_TYPE",
    "CL_DEVICE_TYPE_GPU",
    "CL_DEVICE_UUID_KHR",
    "CL_DEVICE_VENDOR",
    "CL_INVALID_VALUE",
    "CL_MEM_READ_WRITE",
    "CL_PLATFORM_NAME",
    "CL_PLATFORM_VENDOR",
    "CL_PROGRAM_BUILD_LOG",
    "CL_TRUE",
    "OpenCLUnsignedLong",
    "OpenCLBindings",
    "check_opencl_result",
)

CL_SUCCESS = 0
CL_DEVICE_NOT_FOUND = -1
CL_DEVICE_NOT_AVAILABLE = -2
CL_OUT_OF_RESOURCES = -5
CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST = -14
CL_INVALID_VALUE = -30
CL_DEVICE_TYPE_GPU = 4
CL_PLATFORM_NAME = 0x0902
CL_PLATFORM_VENDOR = 0x0903
CL_DEVICE_TYPE = 0x1000
CL_DEVICE_VENDOR = 0x102C
CL_DEVICE_NAME = 0x102B
CL_DEVICE_DRIVER_VERSION = 0x102D
CL_DEVICE_MAX_MEM_ALLOC_SIZE = 0x1010
CL_DEVICE_GLOBAL_MEM_SIZE = 0x101F
CL_DEVICE_UUID_KHR = 0x106A
CL_DEVICE_PCI_BUS_ID_NV = 0x4008
CL_DEVICE_PCI_SLOT_ID_NV = 0x4009
CL_DEVICE_TOPOLOGY_AMD = 0x4037
CL_DEVICE_TOPOLOGY_TYPE_PCIE_AMD = 1
CL_DEVICE_PCI_BUS_INFO_KHR = 0x410F
CL_MEM_READ_WRITE = 1
CL_PROGRAM_BUILD_LOG = 0x1183
CL_TRUE = 1
OpenCLUnsignedLong = ctypes.c_ulonglong


@dataclass(frozen=True, slots=True)
class OpenCLBindings:
    library: ctypes.CDLL

    def __post_init__(self) -> None:
        try:
            self.library.clGetPlatformIDs.argtypes = [
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_uint),
            ]
            self.library.clGetPlatformIDs.restype = ctypes.c_int
            self.library.clGetPlatformInfo.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self.library.clGetPlatformInfo.restype = ctypes.c_int
            self.library.clGetDeviceIDs.argtypes = [
                ctypes.c_void_p,
                OpenCLUnsignedLong,
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_uint),
            ]
            self.library.clGetDeviceIDs.restype = ctypes.c_int
            self.library.clGetDeviceInfo.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self.library.clGetDeviceInfo.restype = ctypes.c_int
            self.library.clCreateContext.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int),
            ]
            self.library.clCreateContext.restype = ctypes.c_void_p
            self.library.clReleaseContext.argtypes = [ctypes.c_void_p]
            self.library.clReleaseContext.restype = ctypes.c_int
            self.library.clCreateCommandQueue.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                OpenCLUnsignedLong,
                ctypes.POINTER(ctypes.c_int),
            ]
            self.library.clCreateCommandQueue.restype = ctypes.c_void_p
            self.library.clReleaseCommandQueue.argtypes = [ctypes.c_void_p]
            self.library.clReleaseCommandQueue.restype = ctypes.c_int
            self.library.clCreateProgramWithSource.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_char_p),
                ctypes.POINTER(ctypes.c_size_t),
                ctypes.POINTER(ctypes.c_int),
            ]
            self.library.clCreateProgramWithSource.restype = ctypes.c_void_p
            self.library.clBuildProgram.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_char_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]
            self.library.clBuildProgram.restype = ctypes.c_int
            self.library.clGetProgramBuildInfo.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_size_t),
            ]
            self.library.clGetProgramBuildInfo.restype = ctypes.c_int
            self.library.clReleaseProgram.argtypes = [ctypes.c_void_p]
            self.library.clReleaseProgram.restype = ctypes.c_int
            self.library.clCreateKernel.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_int),
            ]
            self.library.clCreateKernel.restype = ctypes.c_void_p
            self.library.clReleaseKernel.argtypes = [ctypes.c_void_p]
            self.library.clReleaseKernel.restype = ctypes.c_int
            self.library.clSetKernelArg.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_void_p,
            ]
            self.library.clSetKernelArg.restype = ctypes.c_int
            self.library.clCreateBuffer.argtypes = [
                ctypes.c_void_p,
                OpenCLUnsignedLong,
                ctypes.c_size_t,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_int),
            ]
            self.library.clCreateBuffer.restype = ctypes.c_void_p
            self.library.clReleaseMemObject.argtypes = [ctypes.c_void_p]
            self.library.clReleaseMemObject.restype = ctypes.c_int
            self.library.clEnqueueNDRangeKernel.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_size_t),
                ctypes.POINTER(ctypes.c_size_t),
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]
            self.library.clEnqueueNDRangeKernel.restype = ctypes.c_int
            self.library.clEnqueueReadBuffer.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_size_t,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]
            self.library.clEnqueueReadBuffer.restype = ctypes.c_int
            self.library.clFinish.argtypes = [ctypes.c_void_p]
            self.library.clFinish.restype = ctypes.c_int
            try:
                create_queue_with_properties = self.library.clCreateCommandQueueWithProperties
            except AttributeError:
                create_queue_with_properties = None
            if create_queue_with_properties is not None:
                create_queue_with_properties.argtypes = [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_int),
                ]
                create_queue_with_properties.restype = ctypes.c_void_p
        except AttributeError as exception:
            raise SoAIBenchUnsupported(
                reason="opencl_symbol_missing",
                message=str(exception),
            ) from exception


def check_opencl_result(code: int, reason: str, message: str) -> None:
    if int(code) == CL_SUCCESS:
        return
    if int(code) == CL_DEVICE_NOT_FOUND:
        raise SoAIBenchUnsupported(reason="opencl_gpu_device_unavailable", message=message)
    if int(code) in {
        CL_DEVICE_NOT_AVAILABLE,
        CL_OUT_OF_RESOURCES,
        CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST,
    }:
        raise SoAIBenchUnsupported(
            reason="opencl_device_lost",
            message=f"{message} OpenCL error {int(code)}.",
        )
    raise SoAIBenchUnsupported(reason=reason, message=f"{message} OpenCL error {int(code)}.")
