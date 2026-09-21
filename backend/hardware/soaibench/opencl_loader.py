"""SoAI - SoAIBench OpenCL runtime loader [backend/hardware/soaibench/opencl_loader.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
from ctypes.util import find_library

from core.runtime.opencl_environment import configure_opencl_runtime_environment
from core.runtime.platform import get_runtime_platform
from core.system.windows_ctypes import load_windows_library
from hardware.soaibench.errors import SoAIBenchUnsupported

__all__ = ("load_opencl_library",)


def load_opencl_library() -> ctypes.CDLL:
    configure_opencl_runtime_environment()
    platform = get_runtime_platform()
    names = _candidate_library_names()
    last_error = ""
    for name in names:
        try:
            if platform.is_windows and platform.architecture not in {"arm64", "aarch64"}:
                return load_windows_library(name)
            return ctypes.CDLL(name)
        except OSError as exception:
            last_error = str(exception)
    raise SoAIBenchUnsupported(
        reason="opencl_loader_missing",
        message=last_error or "OpenCL runtime library was not found.",
    )


def _candidate_library_names() -> tuple[str, ...]:
    platform = get_runtime_platform()
    if platform.is_windows:
        return ("OpenCL.dll",)
    if platform.is_macos:
        library_name = find_library("OpenCL")
        framework_path = os.path.join(
            os.path.sep,
            "System",
            "Library",
            "Frameworks",
            "OpenCL.framework",
            "OpenCL",
        )
        if library_name:
            return _unique_library_names((library_name, framework_path))
        return (framework_path,)
    return ("libOpenCL.so.1", "libOpenCL.so")


def _unique_library_names(names: tuple[str, ...]) -> tuple[str, ...]:
    unique_names: list[str] = []
    for name in names:
        if name not in unique_names:
            unique_names.append(name)
    return tuple(unique_names)
