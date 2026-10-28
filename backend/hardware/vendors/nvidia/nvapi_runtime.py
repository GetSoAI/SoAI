"""SoAI - Deferred Windows NvAPI runtime bridge [backend/hardware/vendors/nvidia/nvapi_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from collections.abc import Callable
from importlib.util import find_spec, module_from_spec
from types import ModuleType

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.imports.availability import module_available
from core.logging.protocols import TraceLogger
from core.runtime.platform import RuntimePlatform
from hardware.vendors.nvidia.internal_protocols import (
    NvApiNativeLibraryProtocol,
    NvApiNativeModuleProtocol,
    NvApiRuntimeProtocol,
)

__all__ = ("DeferredNvApiSupport",)

OPERATION_HARDWARE_NVIDIA_NVAPI_RUNTIME_INITIALIZE = "hardware.nvidia.nvapi_runtime.initialize"


def _load_module(module_name: str) -> ModuleType:
    spec = find_spec(module_name)
    if spec is None or spec.loader is None:
        raise StateError(f"Failed to load module spec for {module_name}.")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pynvraw_modules() -> NvApiNativeModuleProtocol:
    if find_spec("pynvraw") is None:
        raise StateError("pynvraw unavailable: missing module")
    _load_module("pynvraw.status")
    api_module = _load_module("pynvraw.nvapi_api")
    if not isinstance(api_module, NvApiNativeModuleProtocol):
        raise StateError("pynvraw unavailable: native API module is invalid")
    return api_module


class DeferredNvApiSupport:
    __slots__ = (
        "_api_instance",
        "_available",
        "_can_attempt",
        "_initialized",
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
        self._api_instance: NvApiRuntimeProtocol | None = None
        self._native_query_interface: Callable[[int], int | None] | None = None
        self._initialized = False
        self._available = False
        self._can_attempt = bool(runtime_platform.is_windows and module_available("pynvraw"))
        self._status_message = (
            None
            if (not runtime_platform.is_windows or self._can_attempt)
            else "pynvraw unavailable: missing module"
        )

    @property
    def native_query_interface(self) -> Callable[[int], int | None] | None:
        if not self.ensure_initialized():
            return None
        return self._native_query_interface

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
        if not self._runtime_platform.is_windows:
            return False
        if not self._can_attempt:
            return False
        initialization_failures: tuple[type[Exception], ...] = (StateError, *RECOVERABLE_EXCEPTIONS)
        with self._lock:
            if self._initialized:
                return self._available
            self._initialized = True
            try:
                api_module = _load_pynvraw_modules()
                native_library = api_module.nvapi
                if not isinstance(native_library, NvApiNativeLibraryProtocol) or not callable(
                    native_library.nvapi_QueryInterface
                ):
                    raise StateError("NvAPI native library QueryInterface is invalid.")
                if not isinstance(api_module.NvError, type) or not issubclass(
                    api_module.NvError, Exception
                ):
                    raise StateError("NvAPI native SDK exception family is invalid.")
                if not callable(api_module.NvAPI):
                    raise StateError("NvAPI native SDK initialization factory is invalid.")
                try:
                    api_instance = api_module.NvAPI()
                except api_module.NvError as exception:
                    raise StateError(
                        "NvAPI native SDK initialization failed.", cause=exception
                    ) from exception
                if not isinstance(api_instance, NvApiRuntimeProtocol):
                    raise StateError("NvAPI native SDK lifetime authority is invalid.")
                self._api_instance = api_instance
                self._native_query_interface = native_library.nvapi_QueryInterface
                self._available = True
                self._status_message = None
                self._logger.info("NvAPI support enabled for Windows GeForce GPU control")
                return True
            except initialization_failures as exception:
                log_handled_exception(
                    self._logger,
                    exception,
                    message="NvAPI initialization failed (non-critical).",
                    operation=OPERATION_HARDWARE_NVIDIA_NVAPI_RUNTIME_INITIALIZE,
                    level="trace",
                )
                self._available = False
                self._status_message = "NvAPI initialization failed."
                return False
