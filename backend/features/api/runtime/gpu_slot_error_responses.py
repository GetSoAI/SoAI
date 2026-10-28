"""SoAI - GPU slot mutation API error projection [backend/features/api/runtime/gpu_slot_error_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from core.errors.exception_logging import log_exception
from core.hardware.gpu_slot_failures import build_gpu_slot_failure_error
from core.logging.trace import get_logger
from core.runtime.protocols import ConnectionProtocol
from core.runtime.request_trace_id import get_request_trace_id
from core.types.json import JSONDict

LOGGER_NAME = "SoAI.features.api.gpu_slot_error_responses"
OPERATION_API_HARDWARE_GPU_SLOT_OPERATION = "api_hardware.gpu.slot_operation"


__all__ = ("raise_slot_operation_error",)


def raise_slot_operation_error(request: ConnectionProtocol, result: JSONDict) -> NoReturn:
    error = build_gpu_slot_failure_error(
        result,
        trace_id=get_request_trace_id(request),
        operation="api_hardware.gpu.slot_operation",
    )
    log_exception(
        get_logger(LOGGER_NAME),
        error,
        message="GPU slot operation failed.",
        operation=OPERATION_API_HARDWARE_GPU_SLOT_OPERATION,
        trace_id=error.trace_id,
        level="error" if error.http_status >= 500 else "debug",
    )
    raise error
