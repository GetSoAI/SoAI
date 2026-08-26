"""SoAI - Internal protocols for GPU tuning helpers [backend/hardware/gpu_tuning/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from core.events.protocols import EventBusProtocol
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.hardware.protocols_activity import HardwareActivityRegistryProtocol
from core.logging.protocols import TraceLogger
from core.system.protocols import CommandExecutorProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.types.json import JSONDict
from hardware.gpu_tuning.gpu_settings import GpuSettingsApplyDependencies
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.vendors.nvidia.smi import NvidiaSettingsController

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("HardwareGpuTuningMutationServiceProtocol",)


class HardwareGpuTuningMutationServiceProtocol(Protocol):
    logger: TraceLogger
    executor: CommandExecutorProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    event_bus: EventBusProtocol | None
    storage: GpuSlotStorageManagerProtocol
    dirty_flag_path: str
    detailed_gpu_info: bool
    main_loop: asyncio.AbstractEventLoop | None
    nvidia_settings_controller: NvidiaSettingsController | None
    gpu_services: GpuServiceDependencies
    gpu_settings_apply_deps: GpuSettingsApplyDependencies
    gpu_capabilities_probe_timeout_seconds: float
    gpu_slots_path: str
    runtime_flags: RuntimeFlagsViewProtocol

    @property
    def gpu_operation_lock(self) -> asyncio.Lock: ...

    @property
    def activity_registry(self) -> HardwareActivityRegistryProtocol: ...

    async def apply_gpu_settings_direct(self, device_id: str, settings: JSONDict) -> JSONDict: ...
    async def apply_gpu_settings_direct_unlocked(
        self,
        device_id: str,
        settings: JSONDict,
    ) -> JSONDict: ...

    async def get_cached_gpu_capabilities(self) -> JSONDict | None: ...
    async def get_gpu_capabilities(self) -> JSONDict: ...
    def reschedule_gpu_capabilities_refresh(self) -> None: ...
    def invalidate_gpu_caches(self) -> None: ...
    def enrich_gpu_capabilities(self, capabilities: JSONDict) -> JSONDict: ...
