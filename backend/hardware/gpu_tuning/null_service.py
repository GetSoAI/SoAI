"""SoAI - Disabled GPU tuning service [backend/hardware/gpu_tuning/null_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.hardware.types import GPUSettingsOutcome
from core.logging.protocols import TraceLogger

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "NullHardwareGpuTuningService",
    "NullHardwareGpuTuningServiceDependencies",
)

OPERATION_NULL_GPU_SLOT_STORE = "hardware.gpu_tuning.null_slot_store"
OPERATION_NULL_GPU_SLOT_APPLY = "hardware.gpu_tuning.null_slot_apply"


@dataclass(frozen=True, slots=True)
class NullHardwareGpuTuningServiceDependencies:
    logger: TraceLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="NullHardwareGpuTuningServiceDependencies",
            logger=self.logger,
        )


class NullHardwareGpuTuningService:
    def __init__(self, deps: NullHardwareGpuTuningServiceDependencies) -> None:
        self.logger: TraceLogger = deps.logger
        self._gpu_operation_lock = asyncio.Lock()

    @property
    def gpu_operation_lock(self) -> asyncio.Lock:
        return self._gpu_operation_lock

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        del loop

    def enrich_gpu_capabilities(self, capabilities: JSONDict) -> JSONDict:
        return capabilities

    async def get_gpu_capabilities(self) -> JSONDict:
        return {}

    async def process_gpu_settings_request(
        self,
        payload: Mapping[str, JSONValue],
    ) -> GPUSettingsOutcome:
        _ = payload
        return GPUSettingsOutcome(
            success=False,
            status_code=503,
            payload={},
            audit_action="gpu_settings_unavailable",
            audit_target="null_hardware_gpu_tuning",
            audit_details={},
            error_type="hardware_unavailable",
            error_message="Hardware manager is not available in this configuration.",
        )

    async def list_gpu_slots(self, device_id: str | None = None) -> JSONDict:
        _ = device_id
        return {
            "success": False,
            "code": "hardware_unavailable",
            "error": "GPU tuning is not available in this configuration.",
        }

    async def preview_gpu_slot(self, device_id: str, slot: str | int) -> JSONDict:
        _ = (device_id, slot)
        raise ValidationError("Hardware manager is not available.")

    async def store_gpu_slot(
        self,
        device_id: str,
        slot: str | int,
        settings: Mapping[str, JSONValue],
        field_modes: Mapping[str, JSONValue] | None = None,
        apply_at_boot: bool | None = None,
    ) -> JSONDict:
        _ = (device_id, slot, settings, field_modes, apply_at_boot)
        return await self._reject_gpu_slot_operation(OPERATION_NULL_GPU_SLOT_STORE)

    async def toggle_gpu_slot_boot(
        self,
        device_id: str,
        slot: str | int,
        enabled: bool,
    ) -> JSONDict:
        _ = (device_id, slot, enabled)
        raise ValidationError("Hardware manager is not available.")

    async def clear_gpu_slot(self, device_id: str, slot: str | int) -> JSONDict:
        _ = (device_id, slot)
        raise ValidationError("Hardware manager is not available.")

    async def apply_gpu_slot(
        self,
        device_id: str,
        slot: str | int,
        apply_at_boot: bool | None = None,
    ) -> JSONDict:
        _ = (device_id, slot, apply_at_boot)
        return await self._reject_gpu_slot_operation(OPERATION_NULL_GPU_SLOT_APPLY)

    async def apply_gpu_settings_direct(self, device_id: str, settings: JSONDict) -> JSONDict:
        _ = (device_id, settings)
        raise ValidationError("Hardware manager is not available.")

    async def apply_gpu_settings_direct_unlocked(
        self,
        device_id: str,
        settings: JSONDict,
    ) -> JSONDict:
        _ = (device_id, settings)
        raise ValidationError("Hardware manager is not available.")

    def invalidate_gpu_caches(self) -> None:
        return

    async def _reject_gpu_slot_operation(self, operation_name: str) -> JSONDict:
        raise ValidationError(
            "Hardware manager is not available.",
            operation=operation_name,
        )

    async def apply_startup_gpu_settings(self) -> None:
        return

    async def clear_dirty_shutdown_flag(self) -> None:
        return
