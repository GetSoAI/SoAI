"""SoAI - Strict fresh Windows physical acquisition [backend/hardware/gpu_inventory/windows_physical_acquisition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError, SoAITimeoutError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_inventory_errors import gpu_inventory_query_failure
from core.hardware.gpu_physical_identity import GPUInventoryReadState
from core.logging.trace import get_logger
from core.serialization.json_parsing import parse_json_value
from core.validation.strings import coerce_optional_trimmed_str
from hardware.gpu_inventory.windows_adapters import WINDOWS_VIDEO_CONTROLLER_QUERY
from hardware.windows_commands import build_windows_powershell_command

if TYPE_CHECKING:
    from core.hardware.gpu_inventory_errors import GPUInventoryQueryFailureReason
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "LOGGER_NAME",
    "OPERATION",
    "WMI_QUERY_FAILURES",
    "WindowsPhysicalAcquisition",
    "read_windows_physical_acquisition",
)

LOGGER_NAME = "SoAI.hardware.gpu_inventory.windows_physical_acquisition"
OPERATION = "hardware.gpu_inventory.windows_physical_acquisition"
WMI_QUERY_FAILURES: tuple[type[Exception], ...] = (*RECOVERABLE_EXCEPTIONS, OSError)


@dataclass(frozen=True, slots=True)
class WindowsPhysicalAcquisition:
    records: tuple[JSONDict, ...]
    state: GPUInventoryReadState
    reason_code: str | None
    raw_output: str | None
    diagnostics: tuple[SoAIError, ...]


def read_windows_physical_acquisition(
    executor: CommandExecutorProtocol,
) -> WindowsPhysicalAcquisition:
    try:
        result = executor.execute(
            build_windows_powershell_command(WINDOWS_VIDEO_CONTROLLER_QUERY),
            timeout=30,
            shell=False,
            use_sudo=False,
        )
    except WMI_QUERY_FAILURES as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Windows GPU inventory query failed.",
            operation=OPERATION,
            level="warning",
        )
        state = GPUInventoryReadState.QUERY_FAILED
        failure_reason: GPUInventoryQueryFailureReason = "query_unavailable"
        reason = "wmi_query_unavailable"
        if isinstance(exception, PermissionError):
            state = GPUInventoryReadState.PERMISSION_DENIED
            failure_reason = "permission_denied"
        elif isinstance(exception, FileNotFoundError):
            state = GPUInventoryReadState.RUNTIME_UNAVAILABLE
            failure_reason = "runtime_unavailable"
        elif isinstance(exception, TimeoutError | SoAITimeoutError):
            failure_reason = "native_timeout"
            reason = "wmi_query_timeout"
        error = gpu_inventory_query_failure(failure_reason, cause=exception)
        return WindowsPhysicalAcquisition((), state, reason, None, (error,))
    if result is None:
        error = StateError("GPU inventory executor returned no response.", operation=OPERATION)
        log_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Windows GPU response is missing.",
            operation=OPERATION,
        )
        return WindowsPhysicalAcquisition(
            (), GPUInventoryReadState.INVALID_RESPONSE, "wmi_response_missing", None, (error,)
        )
    response_details: JSONDict = {
        "return_code": result.return_code,
        "stderr": result.stderr,
        "stdout": result.stdout,
    }
    if (
        result.startup_failure
        or result.timed_out
        or result.return_code != 0
        or not result.stdout.strip()
    ):
        state = GPUInventoryReadState.QUERY_FAILED
        if result.startup_failure == "permission_denied":
            state = GPUInventoryReadState.PERMISSION_DENIED
            reason, failure_reason = "wmi_access_denied", "permission_denied"
        elif result.startup_failure:
            state = GPUInventoryReadState.RUNTIME_UNAVAILABLE
            reason, failure_reason = "wmi_runtime_unavailable", "runtime_unavailable"
        elif result.timed_out:
            reason, failure_reason = "wmi_query_timeout", "native_timeout"
        elif result.return_code:
            reason, failure_reason = "wmi_query_failed", "native_exit"
        else:
            state = GPUInventoryReadState.INVALID_RESPONSE
            reason, failure_reason = "wmi_response_empty", "empty_response"
        error = gpu_inventory_query_failure(failure_reason, details=response_details)
        log_handled_exception(
            get_logger(LOGGER_NAME),
            error,
            message="Windows GPU response is unavailable.",
            operation=OPERATION,
            level="warning",
        )
        return WindowsPhysicalAcquisition((), state, reason, result.stdout, (error,))
    try:
        parsed = parse_json_value(
            result.stdout, field="Win32_VideoController output", reject_duplicate_keys=True
        )
    except ValidationError as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to parse GPU info JSON",
            operation=OPERATION,
            details=response_details,
        )
        return WindowsPhysicalAcquisition(
            (),
            GPUInventoryReadState.INVALID_RESPONSE,
            "wmi_response_invalid",
            result.stdout,
            (exception,),
        )
    records, diagnostics = _read_wmi_records(parsed)
    for diagnostic in diagnostics:
        log_exception(
            get_logger(LOGGER_NAME),
            diagnostic,
            message="Windows GPU row cannot establish complete coverage.",
            operation=OPERATION,
        )
    return WindowsPhysicalAcquisition(
        tuple(records),
        GPUInventoryReadState.INVALID_RESPONSE if diagnostics else GPUInventoryReadState.OBSERVED,
        "wmi_response_invalid" if diagnostics else None,
        result.stdout,
        diagnostics,
    )


def _read_wmi_records(parsed: JSONValue) -> tuple[list[JSONDict], tuple[SoAIError, ...]]:
    records: list[JSONDict] = []
    diagnostics: list[SoAIError] = []
    identifiers: set[str] = set()
    for row in parsed if isinstance(parsed, list) else [parsed]:
        identifier = None
        if isinstance(row, dict):
            identifier = coerce_optional_trimmed_str(
                row.get("PNPDeviceID")
            ) or coerce_optional_trimmed_str(row.get("DeviceID"))
        if (
            not isinstance(row, dict)
            or identifier is None
            or identifier.casefold() in identifiers
            or any(
                row.get(field) is not None and not isinstance(row[field], str)
                for field in ("PNPDeviceID", "DeviceID", "Name")
            )
        ):
            diagnostics.append(
                ValidationError(
                    "Windows GPU inventory row is invalid or duplicated.",
                    operation=OPERATION,
                    details={"raw_row": row},
                )
            )
            continue
        identifiers.add(identifier.casefold())
        records.append(row)
    return records, tuple(diagnostics)
