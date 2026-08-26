"""SoAI - NVIDIA GPU discovery and classification utilities [backend/hardware/vendors/nvidia/discovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.imports.availability import module_available
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from core.system.commands import run_argv_capture

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimePlatformViewProtocol
    from hardware.vendors.nvidia.nvml import NvmlDeviceHandle

__all__ = (
    "NvidiaControlMethod",
    "NvidiaGpuClass",
    "NvidiaGpuClassification",
    "classify_nvidia_gpu",
    "query_nvidia_smi_ecc_support",
    "query_nvidia_smi_gpu_name",
    "read_nvml_ecc_support",
    "resolve_nvidia_control_method",
)

LOGGER_NAME = "SoAI.hardware.vendors.discovery"
OPERATION = "hardware.nvidia.discovery.check_ecc_support"


pynvml_module_ref = None
if module_available("pynvml"):
    import pynvml

    pynvml_module_ref = pynvml


def _pynvml_available() -> bool:
    return pynvml_module_ref is not None


class NvidiaGpuClass(Enum):
    PROFESSIONAL = "professional"
    CONSUMER = "consumer"
    UNKNOWN = "unknown"


class NvidiaControlMethod(Enum):
    PYNVML = "pynvml"
    NVIDIA_SETTINGS = "nvidia_settings"
    NVAPI = "nvapi"
    NONE = "none"


@dataclass(slots=True)
class NvidiaGpuClassification:
    gpu_class: NvidiaGpuClass
    control_method: NvidiaControlMethod
    ecc_supported: bool
    name: str
    vendor_id: int
    reasoning: str
    control_reasoning: str


def normalize_gpu_name(name_value: str | bytes) -> str:
    if isinstance(name_value, bytes):
        return name_value.decode("utf-8", "ignore")
    return name_value


PROFESSIONAL_GPU_PATTERN_TEXTS: tuple[str, ...] = (
    "\\bTesla\\b",
    "\\bQuadro\\b",
    "\\bGrid\\b",
    "\\bNVS\\s+\\d{2,4}\\b",
    "\\bRTX\\s+A\\d{4}",
    "\\bRTX\\s+\\d{4}\\b.*\\bAda\\b",
    "\\bRTX\\s+Pro\\s+\\d{4}",
    "\\bA\\d{1,3}\\b",
    "\\bH\\d{2,3}\\b",
    "\\bB\\d{2,3}\\b",
    "\\bGB\\d{2,3}\\b",
    "\\bL\\d{1,2}S?\\b",
    "\\bT\\d{1,2}\\b",
    "\\bV\\d{2,3}\\b",
)
CONSUMER_GPU_PATTERN_TEXTS: tuple[str, ...] = (
    "\\bGeForce\\b",
    "\\bGT\\s+\\d{3,4}\\b",
    "\\bGTX\\s+\\d{3,4}\\b",
    "\\bMX\\s*\\d{2,4}\\b",
    "\\bRTX\\s+(20|30|40|50|60|70)\\d{2}\\b",
    "\\bTitan\\s+(X|Xp|RTX|V)\\b",
    "\\bGTX\\s+Titan\\b",
    "\\bCMP\\s+\\d+HX\\b",
    "\\bP106[-\\s]?100\\b",
    "\\bM40\\b",
)


def read_nvml_ecc_support(handle: NvmlDeviceHandle) -> bool:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        return False
    logger = get_logger(LOGGER_NAME)
    try:
        nvml_device_get_ecc_mode = pynvml_module.nvmlDeviceGetEccMode
    except AttributeError:
        nvml_device_get_ecc_mode = None
    if not callable(nvml_device_get_ecc_mode):
        return False
    try:
        nvml_device_get_ecc_mode(handle)
        return True
    except pynvml_module.NVMLError:
        return False
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="NVML ECC mode query failed (non-critical).",
            operation=OPERATION,
            level="trace",
        )
        return False


def query_nvidia_smi_gpu_name(vendor_id: int) -> str | None:
    result = run_argv_capture(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        timeout=5,
    )
    if result.return_code != 0:
        return None
    gpu_names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if vendor_id < 0 or vendor_id >= len(gpu_names):
        return None
    return gpu_names[vendor_id]


def query_nvidia_smi_ecc_support(vendor_id: int) -> bool | None:
    result = run_argv_capture(
        ["nvidia-smi", "--query-gpu=ecc.mode.current", "--format=csv,noheader"],
        timeout=5,
    )
    if result.return_code != 0:
        return None
    ecc_modes = [line.strip().lower() for line in result.stdout.splitlines() if line.strip()]
    if vendor_id < 0 or vendor_id >= len(ecc_modes):
        return None
    ecc_mode = ecc_modes[vendor_id]
    if ecc_mode in {"enabled", "disabled"}:
        return True
    if ecc_mode in {"n/a", "not supported"}:
        return False
    return None


def _classify_nvidia_gpu_class(
    name: str,
    *,
    ecc_supported_hint: bool | None,
) -> tuple[NvidiaGpuClass, bool, str]:
    ecc_supported = bool(ecc_supported_hint)
    if ecc_supported:
        return (NvidiaGpuClass.PROFESSIONAL, True, "ECC memory support detected")
    for pattern_text in PROFESSIONAL_GPU_PATTERN_TEXTS:
        if re.search(pattern_text, name, re.IGNORECASE):
            return (
                NvidiaGpuClass.PROFESSIONAL,
                False,
                f"Name matches professional pattern: {pattern_text}",
            )
    for pattern_text in CONSUMER_GPU_PATTERN_TEXTS:
        if re.search(pattern_text, name, re.IGNORECASE):
            return (
                NvidiaGpuClass.CONSUMER,
                False,
                f"Name matches consumer pattern: {pattern_text}",
            )
    return (NvidiaGpuClass.UNKNOWN, False, "No matching pattern found")


def resolve_nvidia_control_method(
    *,
    runtime_platform: RuntimePlatformViewProtocol | None = None,
    nvidia_settings_available: bool = False,
    nvml_available: bool = True,
    nvapi_available: bool = False,
) -> tuple[NvidiaControlMethod, str]:
    effective_platform = (
        runtime_platform if runtime_platform is not None else get_runtime_platform()
    )
    if effective_platform.is_windows and nvapi_available:
        return (NvidiaControlMethod.NVAPI, "NvAPI configured for deferred Windows control")
    if effective_platform.is_linux and nvidia_settings_available:
        return (
            NvidiaControlMethod.NVIDIA_SETTINGS,
            "Linux NVIDIA GPU with nvidia-settings available",
        )
    if nvml_available:
        return (NvidiaControlMethod.PYNVML, "NVML available")
    return (NvidiaControlMethod.NONE, "No supported NVIDIA control backend available")


def classify_nvidia_gpu(
    name: str,
    vendor_id: int = 0,
    *,
    ecc_supported_hint: bool | None = None,
    runtime_platform: RuntimePlatformViewProtocol | None = None,
    nvidia_settings_available: bool = False,
    nvml_available: bool = True,
    nvapi_available: bool = False,
) -> NvidiaGpuClassification:
    gpu_class, ecc_supported, reasoning = _classify_nvidia_gpu_class(
        name,
        ecc_supported_hint=ecc_supported_hint,
    )
    control_method, control_reasoning = resolve_nvidia_control_method(
        runtime_platform=runtime_platform,
        nvidia_settings_available=nvidia_settings_available,
        nvml_available=nvml_available,
        nvapi_available=nvapi_available,
    )
    return NvidiaGpuClassification(
        gpu_class=gpu_class,
        control_method=control_method,
        ecc_supported=ecc_supported,
        name=name,
        vendor_id=vendor_id,
        reasoning=reasoning,
        control_reasoning=control_reasoning,
    )
