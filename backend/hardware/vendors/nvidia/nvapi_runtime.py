"""SoAI - Deferred Windows NvAPI runtime bridge [backend/hardware/vendors/nvidia/nvapi_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from dataclasses import dataclass
from importlib.util import find_spec, module_from_spec
from types import ModuleType
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.imports.availability import module_available
from core.logging.protocols import TraceLogger
from core.runtime.platform import RuntimePlatform
from hardware.vendors.nvidia.internal_protocols import (
    NvApiClocksFactoryProtocol,
    NvApiFactoryProtocol,
    NvApiGpuFactoryProtocol,
    NvApiGpuModuleProtocol,
    NvApiPythonModuleProtocol,
    NvApiRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.hardware.protocols import NvApiClocksProtocol, NvApiGpuProtocol

__all__ = ("DeferredNvApiSupport",)

OPERATION_HARDWARE_NVIDIA_NVAPI_RUNTIME_INITIALIZE = "hardware.nvidia.nvapi_runtime.initialize"
OPERATION_HARDWARE_NVIDIA_NVAPI_RUNTIME_GET_GPU = "hardware.nvidia.nvapi_runtime.get_gpu"


@dataclass(frozen=True, slots=True)
class _LoadedPynvrawModules:
    nvapi_api_module: NvApiPythonModuleProtocol
    gpu_module: NvApiGpuModuleProtocol


def _load_module(module_name: str) -> ModuleType:
    spec = find_spec(module_name)
    if spec is None or spec.loader is None:
        raise StateError(f"Failed to load module spec for {module_name}.")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pynvraw_modules() -> _LoadedPynvrawModules:
    if find_spec("pynvraw") is None:
        raise StateError("pynvraw unavailable: missing module")
    _load_module("pynvraw.status")
    nvapi_api_module = _load_module("pynvraw.nvapi_api")
    gpu_module = _load_module("pynvraw.gpu")
    if not isinstance(nvapi_api_module, NvApiPythonModuleProtocol):
        raise StateError("pynvraw unavailable: invalid nvapi_api module")
    if not isinstance(gpu_module, NvApiGpuModuleProtocol):
        raise StateError("pynvraw unavailable: invalid gpu module")
    return _LoadedPynvrawModules(
        nvapi_api_module=nvapi_api_module,
        gpu_module=gpu_module,
    )


class DeferredNvApiSupport:
    __slots__ = (
        "_api_instance",
        "_available",
        "_can_attempt",
        "_gpu_module",
        "_initialized",
        "_lock",
        "_logger",
        "_runtime_platform",
        "_status_message",
    )

    def __init__(self, *, logger: TraceLogger, runtime_platform: RuntimePlatform) -> None:
        self._lock = threading.Lock()
        self._logger = logger
        self._runtime_platform = runtime_platform
        self._api_instance: NvApiRuntimeProtocol | None = None
        self._gpu_module: NvApiGpuModuleProtocol | None = None
        self._initialized = False
        self._available = False
        self._can_attempt = bool(runtime_platform.is_windows and module_available("pynvraw"))
        self._status_message = (
            None
            if (not runtime_platform.is_windows or self._can_attempt)
            else "pynvraw unavailable: missing module"
        )

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
        with self._lock:
            if self._initialized:
                return self._available
            self._initialized = True
            try:
                loaded_modules = _load_pynvraw_modules()
                typed_api_factory: NvApiFactoryProtocol = loaded_modules.nvapi_api_module.NvAPI
                api_instance = typed_api_factory()
                self._api_instance = api_instance
                self._gpu_module = loaded_modules.gpu_module
                self._available = True
                self._status_message = None
                self._logger.info("NvAPI support enabled for Windows GeForce GPU control")
                return True
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    self._logger,
                    exception,
                    message="NvAPI initialization failed (non-critical).",
                    operation=OPERATION_HARDWARE_NVIDIA_NVAPI_RUNTIME_INITIALIZE,
                    level="trace",
                )
                self._available = False
                self._status_message = f"NvAPI initialization failed: {exception}"
                return False

    def get_phys_gpu(self, vendor_id: int) -> NvApiGpuProtocol | None:
        if not self.ensure_initialized():
            return None
        api_instance = self._api_instance
        gpu_module = self._gpu_module
        if api_instance is None or gpu_module is None:
            return None
        try:
            gpu_handles = api_instance.gpu_handles
            if vendor_id < 0 or vendor_id >= len(gpu_handles):
                return None
            typed_gpu_factory: NvApiGpuFactoryProtocol = gpu_module.Gpu
            return typed_gpu_factory(gpu_handles[vendor_id], api_instance)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                self._logger,
                exception,
                message="NvAPI failed to resolve physical GPU handle (non-critical).",
                operation=OPERATION_HARDWARE_NVIDIA_NVAPI_RUNTIME_GET_GPU,
                details={"vendor_id": vendor_id},
                level="trace",
            )
            return None

    def build_clocks(self, *, core: int, memory: int) -> NvApiClocksProtocol | None:
        if not self.ensure_initialized():
            return None
        gpu_module = self._gpu_module
        if gpu_module is None:
            return None
        typed_clocks_factory: NvApiClocksFactoryProtocol = gpu_module.Clocks
        return typed_clocks_factory(core=core, memory=memory, processor=None, video=None)

    def restore_coolers(self, handle: int) -> None:
        if not self.ensure_initialized():
            raise StateError("NvAPI not available on this platform.")
        api_instance = self._api_instance
        if api_instance is None:
            raise StateError("NvAPI not available on this platform.")
        api_instance.restore_coolers(handle)
