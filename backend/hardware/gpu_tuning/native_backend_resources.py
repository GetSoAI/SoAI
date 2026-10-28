"""SoAI - Requested native resources and original recovery lifetime [backend/hardware/gpu_tuning/native_backend_resources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from typing import Literal

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import TraceLogger
from core.system.protocols import CommandExecutorProtocol
from hardware.gpu_tuning.native_backend_execution import NativeBackendExecution
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.vendors.amd.adl_session import AdlSession
from hardware.vendors.nvidia import nvml_modern_clock_offsets, tuning_nvml
from hardware.vendors.nvidia.internal_protocols import NvmlControlModuleProtocol
from hardware.vendors.nvidia.settings_control_queries import NvidiaSettingsSession
from hardware.vendors.nvidia.smi_display_environment import (
    DisplaySearchStatus,
    detect_display_environment,
)

__all__ = ("native_backend_resources",)

OPERATION_ORIGINAL_RESOURCE = "hardware.gpu.original_resource"


@contextmanager
def native_backend_resources(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
    backends: tuple[str, ...],
    conversion_fields: tuple[str, ...],
    goal: Literal["requested", "original"],
) -> Generator[NativeBackendExecution]:
    gate = gpu_services.nvidia_nvml_gate
    module: NvmlControlModuleProtocol | None = None
    query_interface: Callable[[int], int | None] | None = None
    settings_session: NvidiaSettingsSession | None = None
    adl_session: AdlSession | None = None
    native_exceptions: tuple[type[Exception], ...] = ()
    if "nvml" in backends or conversion_fields:
        acquired_module = tuning_nvml.pynvml_module_ref
        if acquired_module is not None:
            native_exceptions = (acquired_module.NVMLError,)
    try:
        with ExitStack() as resources:
            if "nvml" in backends or conversion_fields:
                acquisition_failures: tuple[type[Exception], ...] = (
                    *native_exceptions,
                    *HANDLED_RUNTIME_EXCEPTIONS,
                )
                try:
                    active_module = tuning_nvml.pynvml_module_ref
                    if active_module is None or not gate.nvml_available:
                        raise StateError(
                            "The requested native module or conversion facility is unavailable.",
                        )
                    if not isinstance(active_module, NvmlControlModuleProtocol):
                        raise StateError(
                            "The native SDK module does not expose its declared control ABI."
                        )
                    try:
                        resources.enter_context(gate.session())
                    except active_module.NVMLError as exception:
                        raise StateError(
                            "NVML native session initialization failed.",
                            details={"actuator_invoked": False},
                            cause=exception,
                        ) from exception
                    module = active_module
                except acquisition_failures as exception:
                    if goal == "requested":
                        raise
                    log_exception(
                        logger,
                        exception,
                        message="NVML original recovery resource is unavailable (non-critical).",
                        operation=OPERATION_ORIGINAL_RESOURCE,
                        level="trace",
                    )
            if "nvapi" in backends:
                query_interface = gate.nvapi_support.native_query_interface
            if "nvidia_settings" in backends:
                try:
                    controller = gpu_services.nvidia_settings_controller
                    if controller is not None:
                        display = detect_display_environment(logger, query=controller.native_query)
                        if (
                            display.status == DisplaySearchStatus.USABLE
                            and display.display is not None
                        ):
                            settings_session = NvidiaSettingsSession(
                                controller.native_query, display.display, display.xauthority
                            )
                except HANDLED_RUNTIME_EXCEPTIONS as exception:
                    if goal == "requested":
                        raise
                    log_exception(
                        logger,
                        exception,
                        message="NVIDIA settings original recovery resource is unavailable (non-critical).",
                        operation=OPERATION_ORIGINAL_RESOURCE,
                        level="trace",
                    )
            if "amd_adl" in backends:
                try:
                    runtime = gpu_services.adl_runtime
                    if runtime is None:
                        raise StateError("The app ADL resource owner is unavailable.")
                    adl_session = resources.enter_context(runtime.session())
                except HANDLED_RUNTIME_EXCEPTIONS as exception:
                    if goal == "requested":
                        raise
                    log_exception(
                        logger,
                        exception,
                        message="ADL original recovery resource is unavailable (non-critical).",
                        operation=OPERATION_ORIGINAL_RESOURCE,
                        level="trace",
                    )
            boundary = NativeBackendExecution(
                executor,
                gpu_services,
                module,
                nvml_modern_clock_offsets.native_function_resolver,
                query_interface,
                settings_session,
                goal,
                adl_session,
            )
            yield boundary
    except native_exceptions as exception:
        raise StateError(
            "The native SDK resource lifetime did not complete.",
            details={"possible_effect": "unknown"},
            cause=exception,
        ) from exception
