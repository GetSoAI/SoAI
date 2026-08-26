"""SoAI - NVML isolated preflight child process source [backend/hardware/vendors/nvidia/nvml_preflight_script.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "NVML_PREFLIGHT_EXIT_MODULE_MISSING",
    "NVML_PREFLIGHT_EXIT_NVML_UNAVAILABLE",
    "NVML_PREFLIGHT_EXIT_USABLE",
    "NVML_PREFLIGHT_SCRIPT",
)

NVML_PREFLIGHT_EXIT_USABLE = 0
NVML_PREFLIGHT_EXIT_MODULE_MISSING = 11
NVML_PREFLIGHT_EXIT_NVML_UNAVAILABLE = 12

NVML_PREFLIGHT_SCRIPT = """\
import ctypes
import sys

if sys.platform == "win32":
    ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)

try:
    import pynvml
except ImportError:
    raise SystemExit(11)

try:
    pynvml.nvmlInit()
except pynvml.NVMLError:
    raise SystemExit(12)

reported_errors = []
try:
    try:
        pynvml.nvmlSystemGetDriverVersion()
    except pynvml.NVMLError as exception:
        reported_errors.append(f"driver_version: {exception}")
    try:
        device_count = int(pynvml.nvmlDeviceGetCount())
    except pynvml.NVMLError as exception:
        device_count = 0
        reported_errors.append(f"device_count: {exception}")
    for device_index in range(device_count):
        try:
            device_handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
            pynvml.nvmlDeviceGetName(device_handle)
            pynvml.nvmlDeviceGetMemoryInfo(device_handle)
        except pynvml.NVMLError as exception:
            reported_errors.append(f"device {device_index}: {exception}")
finally:
    try:
        pynvml.nvmlShutdown()
    except pynvml.NVMLError as exception:
        reported_errors.append(f"shutdown: {exception}")

if reported_errors:
    sys.stderr.write("; ".join(reported_errors))
    sys.stderr.write("\\n")
raise SystemExit(0)
"""
