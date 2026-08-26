"""SoAI - NVIDIA NVML runtime gating [backend/hardware/vendors/nvidia/nvml.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.protocols import NvApiSupportProtocol
from core.imports.availability import module_available
from core.logging.trace import TraceLogger
from core.runtime.platform import RuntimePlatform

if TYPE_CHECKING:
    import ctypes

    type NvmlDeviceHandle = ctypes.c_void_p

__all__ = ("NvmlGate",)

OPERATION_HARDWARE_NVIDIA_NVML_SESSION_SHUTDOWN = "hardware.nvidia.nvml.session.shutdown"


pynvml_module = None
if module_available("pynvml"):
    import pynvml

    pynvml_module = pynvml


class NvmlGate:
    logger: TraceLogger
    runtime_platform: RuntimePlatform
    nvapi_support: NvApiSupportProtocol
    nvidia_settings_available: bool
    nvidia_settings_status_message: str | None
    nvml_available: bool

    __slots__ = (
        "_lock",
        "logger",
        "nvapi_support",
        "nvidia_settings_available",
        "nvidia_settings_status_message",
        "nvml_available",
        "runtime_platform",
    )

    def __init__(
        self,
        *,
        logger: TraceLogger,
        runtime_platform: RuntimePlatform,
        nvapi_support: NvApiSupportProtocol,
        nvidia_settings_available: bool,
        nvidia_settings_status_message: str | None,
        nvml_available: bool,
    ) -> None:
        self._lock = threading.Lock()
        self.logger = logger
        self.runtime_platform = runtime_platform
        self.nvapi_support = nvapi_support
        self.nvidia_settings_available = nvidia_settings_available
        self.nvidia_settings_status_message = nvidia_settings_status_message
        self.nvml_available = nvml_available

    @contextmanager
    def session(self) -> Generator[None]:
        if not self.nvml_available:
            raise StateError(
                "NVML is unavailable because the NVML runtime preflight did not report it usable.",
                operation="hardware.nvidia.nvml.session",
            )
        active_pynvml_module = pynvml_module
        if active_pynvml_module is None:
            raise StateError(
                "NVML is unavailable because pynvml (nvidia-ml-py) is not installed.",
                operation="hardware.nvidia.nvml.session",
            )
        with self._lock:
            try:
                init_function = active_pynvml_module.nvmlInit
            except AttributeError:
                init_function = None
            try:
                shutdown_function = active_pynvml_module.nvmlShutdown
            except AttributeError:
                shutdown_function = None
            if not callable(init_function) or not callable(shutdown_function):
                raise StateError(
                    "NVML functions are not callable. This indicates a corrupted pynvml installation.",
                    operation="hardware.nvidia.nvml.session",
                )
            init_function()
            try:
                yield
            finally:
                try:
                    shutdown_function()
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        self.logger,
                        exception,
                        message="nvmlShutdown failed (non-critical).",
                        operation=OPERATION_HARDWARE_NVIDIA_NVML_SESSION_SHUTDOWN,
                        level="trace",
                    )
