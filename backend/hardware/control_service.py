"""SoAI - Internal hardware control service [backend/hardware/control_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ServiceUnavailableError, ValidationError
from core.errors.public_projection import (
    project_public_exception,
    project_public_status_error,
)
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.protocols import (
    HardwareGpuTuningProtocol,
    HardwareManagerProtocol,
)
from core.logging.protocols import TraceLogger
from core.timing.constants import CONTROL_TIMEOUT_SEC, OCR_TIMEOUT_SEC
from core.types.json_value import copy_json_dict
from hardware.control_snapshots import (
    build_control_list_payload,
    find_gpu_capabilities,
    find_gpu_entry,
)
from hardware.gpu_tuning.mutation_policy import hardware_mutation_disabled_payload
from hardware.gpu_tuning.result_flags import is_success_result
from hardware.validate import sanitize_settings

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict

__all__ = (
    "HardwareControlService",
    "HardwareControlServiceDependencies",
)

OPERATION_HARDWARE_CONTROL_RECOVERY_SNAPSHOT = "hardware.control_service.recovery_snapshot"
OPERATION_HARDWARE_CONTROL_APPLY_SETTINGS = "hardware.control_service.apply_settings"


@dataclass(frozen=True, slots=True)
class HardwareControlServiceDependencies:
    hardware_manager: HardwareManagerProtocol
    gpu_tuning: HardwareGpuTuningProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    logger: TraceLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="HardwareControlServiceDependencies",
            gpu_tuning=self.gpu_tuning,
            hardware_manager=self.hardware_manager,
            logger=self.logger,
            runtime_flags=self.runtime_flags,
        )


class HardwareControlService:
    def __init__(self, deps: HardwareControlServiceDependencies) -> None:
        self._hardware_manager = deps.hardware_manager
        self._gpu_tuning = deps.gpu_tuning
        self._runtime_flags = deps.runtime_flags
        self._logger = deps.logger

    async def list_gpu_controls(self) -> JSONDict:
        async with self._gpu_tuning.gpu_operation_lock:
            snapshot, capabilities = await self._snapshot_and_capabilities()
        payload = build_control_list_payload(snapshot, capabilities)
        payload["action"] = "list"
        return payload

    async def set_gpu_controls(
        self,
        *,
        device_id: str,
        settings: JSONDict,
        created_by_user_id: int,
    ) -> JSONDict:
        _ = created_by_user_id
        if self._runtime_flags.hardware_mutation_disabled:
            return _hardware_mutation_disabled_set_response(device_id)
        async with self._gpu_tuning.gpu_operation_lock:
            if self._runtime_flags.hardware_mutation_disabled:
                return _hardware_mutation_disabled_set_response(device_id)
            before_snapshot, capabilities = await self._snapshot_and_capabilities()
            before_gpu = self._require_gpu(before_snapshot, device_id)
            cap_entry = find_gpu_capabilities(capabilities, before_gpu, device_id)
            normalized_settings = sanitize_settings(settings, cap_entry)
            apply_result = await self._apply_settings(
                device_id,
                normalized_settings,
            )
            after_snapshot = await self._recovering_snapshot()
            after_gpu = find_gpu_entry(after_snapshot, device_id)
            no_op = _is_no_op_result(apply_result)
            status, failure_reason = _classify_apply_status(
                apply_result=apply_result,
                after_gpu=after_gpu,
                no_op=no_op,
                logger=self._logger,
            )
            public_apply_result = _project_public_apply_result(apply_result)
            return {
                "action": "set",
                "device_id": device_id,
                "status": status,
                "before_snapshot": before_gpu,
                "normalized_settings": normalized_settings,
                "apply_result": public_apply_result,
                "after_snapshot": after_gpu,
                "no_op": no_op,
                "failure_reason": failure_reason,
            }

    async def _snapshot_and_capabilities(self) -> tuple[JSONDict, JSONDict]:
        if self._hardware_manager.enabled is False:
            raise ServiceUnavailableError("Hardware manager is not available.")
        snapshot = await asyncio.wait_for(
            self._hardware_manager.get_system_info(components=("gpu",), cache=False),
            timeout=CONTROL_TIMEOUT_SEC,
        )
        capabilities = await asyncio.wait_for(
            self._gpu_tuning.get_gpu_capabilities(),
            timeout=OCR_TIMEOUT_SEC,
        )
        return (snapshot, capabilities)

    async def _recovering_snapshot(self) -> JSONDict:
        self._gpu_tuning.invalidate_gpu_caches()
        try:
            return await asyncio.wait_for(
                self._hardware_manager.get_system_info(components=("gpu",), cache=False),
                timeout=CONTROL_TIMEOUT_SEC,
            )
        except TimeoutError as exception:
            log_exception(
                self._logger,
                exception,
                message="GPU inventory recovery probe timed out after hardware control operation.",
                operation=OPERATION_HARDWARE_CONTROL_RECOVERY_SNAPSHOT,
                level="error",
            )
            return {"gpu": {"gpus": [], "by_device_id": {}}}
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Failed to probe GPU inventory after hardware control operation.",
                operation=OPERATION_HARDWARE_CONTROL_RECOVERY_SNAPSHOT,
                level="error",
            )
            return {"gpu": {"gpus": [], "by_device_id": {}}}

    def _require_gpu(self, snapshot: JSONDict, device_id: str) -> JSONDict:
        gpu = find_gpu_entry(snapshot, device_id)
        if gpu is None:
            raise ValidationError(f"GPU device is not available: {device_id}")
        return copy_json_dict(gpu)

    async def _apply_settings(self, device_id: str, settings: JSONDict) -> JSONDict:
        try:
            if self._runtime_flags.hardware_mutation_disabled:
                return hardware_mutation_disabled_payload()
            return await self._gpu_tuning.apply_gpu_settings_direct_unlocked(
                device_id,
                settings,
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="GPU settings apply failed during hardware control operation.",
                operation=OPERATION_HARDWARE_CONTROL_APPLY_SETTINGS,
                level="error",
                details={"device_id": device_id},
            )
            return {
                "success": False,
                "code": "gpu_apply_exception",
                "error": project_public_exception(exception).message,
            }


def _is_no_op_result(result: JSONDict) -> bool:
    return result.get("success") is True and result.get("changed") is False


def _hardware_mutation_disabled_set_response(device_id: str) -> JSONDict:
    disabled_payload = hardware_mutation_disabled_payload()
    return {
        "action": "set",
        "device_id": device_id,
        "status": "disabled",
        "before_snapshot": None,
        "normalized_settings": {},
        "apply_result": disabled_payload,
        "after_snapshot": None,
        "no_op": False,
        "failure_reason": disabled_payload["code"],
    }


def _classify_apply_status(
    *,
    apply_result: JSONDict,
    after_gpu: JSONDict | None,
    no_op: bool,
    logger: TraceLogger,
) -> tuple[str, str | None]:
    if apply_result.get("code") == "hardware_mutation_disabled":
        return ("disabled", "hardware_mutation_disabled")
    if after_gpu is None:
        return ("indeterminate", "gpu_device_missing_after_set")
    if "success" not in apply_result and "error" not in apply_result:
        return ("indeterminate", "gpu_apply_result_malformed")
    if no_op:
        return ("no_op", None)
    if not is_success_result(
        apply_result,
        logger=logger,
        operation="hardware.control_service.apply_success",
    ):
        return ("failed", _coerce_apply_failure_reason(apply_result))
    return ("applied", None)


def _coerce_apply_failure_reason(apply_result: JSONDict) -> str:
    code_value = apply_result.get("code")
    if isinstance(code_value, str) and code_value:
        return code_value
    return "gpu_apply_failed"


def _project_public_apply_result(apply_result: JSONDict) -> JSONDict:
    if apply_result.get("success") is True:
        return copy_json_dict(apply_result)
    code_value = apply_result.get("code")
    code = code_value if isinstance(code_value, str) and code_value else "gpu_apply_failed"
    if code not in {"apply_failed", "gpu_apply_exception"}:
        return copy_json_dict(apply_result)
    public_error = project_public_status_error(
        status_code=500,
        code=code,
        message="GPU settings could not be applied.",
    )
    return {
        "success": False,
        "code": code,
        "error": public_error.to_dict(),
    }
