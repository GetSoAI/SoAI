"""SoAI - Intel GPU settings application [backend/hardware/vendors/intel/settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_operation_results import build_gpu_result
from core.runtime.platform import get_runtime_platform
from hardware.gpu_tuning.settings_request import GpuSettingsApplyRequest
from hardware.result_messages import (
    append_intel_log_message,
    build_gpu_result_message_lists,
)
from hardware.vendors.intel.commands import execute_intel_config_command
from hardware.vendors.intel.runtime import is_xpu_smi_available
from hardware.vendors.intel.settings_resolution import resolve_intel_apply_commands

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("sync_set_intel_settings",)

OPERATION = "hardware_intel.sync_set_intel_settings"
INTEL_SETTING_EXCEPTIONS: tuple[type[Exception], ...] = (
    StateError,
    ValidationError,
    RuntimeError,
    TimeoutError,
    *RECOVERABLE_EXCEPTIONS,
)


def sync_set_intel_settings(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    request: GpuSettingsApplyRequest,
    capabilities: JSONDict | None = None,
) -> JSONDict:
    control_backend = request.control_backend
    if control_backend is None:
        return build_gpu_result(errors=["Intel control backend is required."])
    if control_backend != "intel_xpum":
        return build_gpu_result(
            errors=[f"Intel control backend '{control_backend}' is unsupported."],
        )
    if not is_xpu_smi_available():
        return build_gpu_result(errors=["xpu-smi not found for Intel GPU control."])
    gpu_result, messages, errors = build_gpu_result_message_lists()
    try:
        steps = resolve_intel_apply_commands(executor, logger, vendor_id, request, capabilities)
    except INTEL_SETTING_EXCEPTIONS as exception:
        _append_intel_error(
            errors, logger, exception, vendor_id, "Failed to prepare Intel settings."
        )
        return gpu_result
    use_sudo = not get_runtime_platform().is_windows
    for step in steps:
        if step.args is None:
            errors.append(f"Failed to set {step.label}: {step.message}")
            return gpu_result
        try:
            execute_intel_config_command(executor, vendor_id, step.args, use_sudo=use_sudo)
            gpu_result["changed"] = True
            append_intel_log_message(messages, logger, vendor_id, step.message)
        except INTEL_SETTING_EXCEPTIONS as exception:
            _append_intel_error(
                errors,
                logger,
                exception,
                vendor_id,
                f"Failed to set {step.label}.",
            )
            return gpu_result
    return gpu_result


def _append_intel_error(
    errors: list[str],
    logger: TraceLogger | None,
    exception: Exception,
    vendor_id: int,
    message: str,
) -> None:
    if logger is not None:
        log_exception(
            logger,
            exception,
            message=message,
            operation=OPERATION,
            details={"vendor_id": vendor_id},
            level="warning",
        )
    errors.append(f"{message} {exception}")
