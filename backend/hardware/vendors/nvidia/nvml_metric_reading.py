"""SoAI - NVIDIA NVML metric read operations [backend/hardware/vendors/nvidia/nvml_metric_reading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.imports.availability import module_available
from hardware.vendors.nvidia.internal_protocols import NvmlErrorValueProtocol

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger

__all__ = (
    "is_nvml_error_not_supported",
    "read_nvidia_metric_value",
)

OPERATION = "hardware.nvidia.nvml_metric_reading.read_metric"


pynvml_module_ref = None
if module_available("pynvml"):
    import pynvml

    pynvml_module_ref = pynvml


def is_nvml_error_not_supported(exception: Exception) -> bool:
    active_pynvml_module = pynvml_module_ref
    if active_pynvml_module is None or not isinstance(exception, NvmlErrorValueProtocol):
        return False
    try:
        error_not_supported: int = active_pynvml_module.NVML_ERROR_NOT_SUPPORTED
    except AttributeError:
        return False
    return exception.value == error_not_supported


def read_nvidia_metric_value(
    reader: Callable[[], int | None],
    metric_name: str,
    device_index: int,
    *,
    logger: TraceLogger,
) -> int | None:
    active_pynvml_module = pynvml_module_ref
    if active_pynvml_module is None:
        return None
    try:
        return reader()
    except active_pynvml_module.NVMLError as exception:
        if not is_nvml_error_not_supported(exception):
            logger.trace(
                "Could not read %s for GPU %s: %s",
                metric_name,
                device_index,
                str(exception),
            )
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read NVIDIA metric (non-critical).",
            operation=OPERATION,
            details={"device_index": device_index, "metric": metric_name},
            level="trace",
        )
        return None
