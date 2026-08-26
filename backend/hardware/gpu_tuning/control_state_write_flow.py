"""SoAI - GPU tuning control state write flow [backend/hardware/gpu_tuning/control_state_write_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_operation_results import build_gpu_result
from hardware.gpu_tuning.device_mode_storage import (
    ensure_device_control_state,
    ensure_known_device_control_state,
)

if TYPE_CHECKING:
    from core.hardware.protocols import GpuSlotStorageManagerProtocol
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies

__all__ = (
    "ControlStateWriteFlowResult",
    "sync_write_requested_control_state",
)

CONTROL_STATE_WRITE_ERROR = "Failed to update GPU control modes."


@dataclass(frozen=True, slots=True)
class ControlStateWriteFlowResult:
    success: bool
    changed: bool
    gpu_result: JSONDict


def sync_write_requested_control_state(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    gpu_services: GpuServiceDependencies,
    logger: TraceLogger,
    operation: str,
    device_id: str,
    field_modes: JSONDict,
    applied_settings: JSONDict,
    current_device_info: JSONDict | None = None,
) -> ControlStateWriteFlowResult:
    try:
        if current_device_info is not None:
            write_result = ensure_known_device_control_state(
                storage=storage,
                device_id=device_id,
                device_info=current_device_info,
                field_modes=field_modes,
                applied_settings=applied_settings,
            )
        else:
            write_result = ensure_device_control_state(
                executor=executor,
                storage=storage,
                detailed_gpu_info=detailed_gpu_info,
                gpu_services=gpu_services,
                device_id=device_id,
                field_modes=field_modes,
                applied_settings=applied_settings,
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to update GPU control state.",
            operation=operation,
            details={"device_id": device_id},
            level="trace",
        )
        return ControlStateWriteFlowResult(
            success=False,
            changed=False,
            gpu_result=build_gpu_result(errors=[CONTROL_STATE_WRITE_ERROR], changed=False),
        )
    if not write_result.success:
        return ControlStateWriteFlowResult(
            success=False,
            changed=False,
            gpu_result=build_gpu_result(errors=[CONTROL_STATE_WRITE_ERROR], changed=False),
        )
    return ControlStateWriteFlowResult(
        success=True,
        changed=write_result.changed,
        gpu_result=build_gpu_result(
            messages=["Updated requested GPU control modes."],
            changed=write_result.changed,
        ),
    )
