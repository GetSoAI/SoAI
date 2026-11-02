"""SoAI - Deferred native Windows NvAPI lifetime [backend/hardware/vendors/nvidia/nvapi_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.runtime.platform import RuntimePlatform
from core.system.windows_ctypes import load_windows_system_library

__all__ = ("DeferredNvApiSupport",)

OPERATION_HARDWARE_NVIDIA_NVAPI_RUNTIME_INITIALIZE = "hardware.nvidia.nvapi_runtime.initialize"


class DeferredNvApiSupport:
    __slots__ = (
        "_available",
        "_can_attempt",
        "_initialized",
        "_library",
        "_lock",
        "_native_query_interface",
        "_logger",
        "_runtime_platform",
        "_status_message",
    )

    def __init__(self, *, logger: TraceLogger, runtime_platform: RuntimePlatform) -> None:
        self._lock = threading.Lock()
        self._logger = logger
        self._runtime_platform = runtime_platform
        self._library: ctypes.CDLL | None = None
        self._native_query_interface: Callable[[int], int | None] | None = None
        self._initialized = self._available = False
        self._can_attempt = (
            runtime_platform.is_windows and runtime_platform.architecture_id == "x64"
        )
        self._status_message: str | None = None

    @property
    def native_query_interface(self) -> Callable[[int], int | None] | None:
        return self._native_query_interface if self.ensure_initialized() else None

    @property
    def can_attempt(self) -> bool:
        return self._can_attempt

    @property
    def available(self) -> bool:
        return self._available

    @property
    def status_message(self) -> str | None:
        return self._status_message

    def ensure_initialized(self) -> bool:
        if not self._can_attempt:
            return False
        failures: tuple[type[Exception], ...] = (
            StateError,
            OSError,
            AttributeError,
            ctypes.ArgumentError,
            *RECOVERABLE_EXCEPTIONS,
        )
        with self._lock:
            if self._initialized:
                return self._available
            self._initialized = True
            try:
                library = load_windows_system_library("nvapi64.dll")
                query = library.nvapi_QueryInterface
                query.argtypes = [ctypes.c_uint32]
                query.restype = ctypes.c_void_p
                address = query(0x0150E828)
                if (
                    not isinstance(address, int)
                    or isinstance(address, bool)
                    or not 0 < address < 1 << 64
                ):
                    raise StateError("NvAPI native initialization export is unavailable.")
                initialize = ctypes.CFUNCTYPE(ctypes.c_int32)(address)
                status = initialize()
                if status != 0:
                    raise StateError(
                        "NvAPI native initialization failed.", details={"native_status": status}
                    )
                self._library = library
                self._native_query_interface = query
                self._available = True
                self._logger.info("NvAPI native Windows GPU support enabled")
                return True
            except failures as exception:
                log_handled_exception(
                    self._logger,
                    exception,
                    message="NvAPI initialization failed (non-critical).",
                    operation=OPERATION_HARDWARE_NVIDIA_NVAPI_RUNTIME_INITIALIZE,
                    level="trace",
                )
                self._status_message = "NvAPI initialization failed."
                return False
