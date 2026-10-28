"""SoAI - GPU tuning service with preset slots and settings [backend/hardware/gpu_tuning/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING

from core.hardware.gpu_control_types import GPUControlStartupDisposition, GPUControlStartupResult
from core.hardware.protocols import (
    GPURecoveryAdmissionProtocol,
    GpuSlotStorageManagerProtocol,
    HardwareManagerProtocol,
)
from core.hardware.protocols_activity import HardwareActivityRegistryProtocol
from core.hardware.types import GPUSettingsOutcome
from core.logging.protocols import TraceLogger
from core.runtime.soai_identifiers import create_system_id
from core.system.protocols import CommandExecutorProtocol
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from hardware.control_service import hardware_mutation_disabled_control_response
from hardware.gpu_tuning.capabilities import (
    enrich_gpu_capabilities_with_slots,
)
from hardware.gpu_tuning.capabilities_refresh import (
    refresh_capabilities_after_settings_change,
)
from hardware.gpu_tuning.control_operation_delivery import GPUControlDeliveryDependencies
from hardware.gpu_tuning.control_operation_finalization import GPUControlFinalizationDependencies
from hardware.gpu_tuning.control_operations import drain_control_operations
from hardware.gpu_tuning.dependencies import (
    GpuSettingsApplyDependencies,
    HardwareGpuTuningServiceDependencies,
)
from hardware.gpu_tuning.dirty_shutdown_flag import clear_dirty_shutdown_flag_file
from hardware.gpu_tuning.gpu_settings import (
    build_gpu_settings_apply_dependencies,
)
from hardware.gpu_tuning.leased_mutations import (
    apply_gpu_settings_direct_with_lease,
    apply_gpu_slot_with_lease,
    clear_gpu_slot_with_lease,
    process_gpu_settings_request_with_lease,
    store_gpu_slot_with_lease,
    toggle_gpu_slot_boot_with_lease,
)
from hardware.gpu_tuning.mutation_policy import (
    hardware_mutation_disabled_outcome,
    hardware_mutation_disabled_payload,
)
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.service_mutations import (
    apply_gpu_settings_direct_for_service,
)
from hardware.gpu_tuning.slot_queries import sync_list_gpu_slots, sync_preview_gpu_slot
from hardware.gpu_tuning.snapshot_control import apply_snapshot_gpu_controls
from hardware.gpu_tuning.startup_service import apply_startup_gpu_settings
from hardware.operations import can_emit_events

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict, JSONValue
    from hardware.internal_protocols import GpuCapabilitiesServiceProtocol

__all__ = ("HardwareGpuTuningService",)

GPU_CAPABILITIES_REFRESH_DEBOUNCE_SECONDS = 5.0


class HardwareGpuTuningService:
    def __init__(self, deps: HardwareGpuTuningServiceDependencies) -> None:
        self._deps = deps
        self.logger: TraceLogger = deps.logger
        self.executor: CommandExecutorProtocol = deps.command_executor
        self.cancellation_binder = deps.cancellation_binder
        self.finalizer_tracker = deps.finalizer_tracker
        self.event_bus = deps.event_bus
        self.runtime_flags: RuntimeFlagsViewProtocol = deps.runtime_flags
        self.storage: GpuSlotStorageManagerProtocol = deps.gpu_slot_storage
        self.native_control_recovery = deps.native_control_recovery
        self.control_operation_state = deps.control_operation_state
        self.gpu_slots_path = deps.gpu_slots_path
        self.dirty_flag_path = deps.dirty_flag_path
        self.activity_registry: HardwareActivityRegistryProtocol = deps.activity_registry
        self.detailed_gpu_info = deps.detailed_gpu_info
        self.main_loop: asyncio.AbstractEventLoop | None = None
        self.nvidia_settings_controller = deps.nvidia_settings_controller
        self.gpu_services = GpuServiceDependencies(
            gpu_info_cache_service=deps.gpu_info_cache_service,
            gpu_vendor_detection_service=deps.gpu_vendor_detection_service,
            nvidia_nvml_gate=deps.nvidia_nvml_gate,
            nvidia_settings_controller=deps.nvidia_settings_controller,
            nvidia_capabilities_cache_service=deps.nvidia_capabilities_cache_service,
            nvidia_smi_executable=deps.nvidia_smi_executable,
            intel_executable=deps.intel_executable,
            adl_runtime=deps.adl_runtime,
        )
        self.gpu_settings_apply_deps: GpuSettingsApplyDependencies = (
            build_gpu_settings_apply_dependencies(
                executor=self.executor,
                logger=self.logger,
                storage=self.storage,
                detailed_gpu_info=self.detailed_gpu_info,
                nvidia_settings_controller=self.nvidia_settings_controller,
                gpu_services=self.gpu_services,
                native_control_recovery=self.native_control_recovery,
                control_operation_state=self.control_operation_state,
                runtime_flags=self.runtime_flags,
                delivery_dependencies=GPUControlDeliveryDependencies(
                    GPUControlFinalizationDependencies(self.gpu_services, self.dirty_flag_path),
                    self.logger,
                    self.event_bus,
                    self.main_loop,
                    self.cancellation_binder,
                    self.finalizer_tracker,
                    executor=self.executor,
                ),
            )
        )
        self._gpu_capabilities_service: GpuCapabilitiesServiceProtocol = (
            deps.gpu_capabilities_service
        )
        self._gpu_operation_lock = deps.gpu_operation_lock
        self.gpu_capabilities_probe_timeout_seconds: float = 15.0
        self._gpu_capabilities_refresh_task: asyncio.Task[bool] | None = None

    @property
    def recovery_admission(self) -> GPURecoveryAdmissionProtocol:
        return self.native_control_recovery

    @property
    def gpu_operation_lock(self) -> asyncio.Lock:
        return self._gpu_operation_lock

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.main_loop = loop
        self.gpu_settings_apply_deps = replace(
            self.gpu_settings_apply_deps,
            delivery_dependencies=replace(
                self.gpu_settings_apply_deps.delivery_dependencies, main_loop=loop
            ),
        )

    def enrich_gpu_capabilities(self, capabilities: JSONDict) -> JSONDict:
        return enrich_gpu_capabilities_with_slots(
            self.executor,
            capabilities,
            self.storage,
            self.detailed_gpu_info,
            gpu_services=self.gpu_services,
        )

    async def get_gpu_capabilities(self) -> JSONDict:
        return await self._gpu_capabilities_service.get_capabilities(self.enrich_gpu_capabilities)

    async def get_cached_gpu_capabilities(self) -> JSONDict | None:
        return await self._gpu_capabilities_service.get_cached_capabilities()

    def reschedule_gpu_capabilities_refresh(self) -> None:
        existing_task = self._gpu_capabilities_refresh_task
        if existing_task is not None and not existing_task.done():
            existing_task.cancel()
        self._gpu_capabilities_refresh_task = None
        event_bus = self.event_bus
        if event_bus is None or not can_emit_events(event_bus, self.main_loop):
            return
        self._gpu_capabilities_refresh_task = spawn_tracked_task(
            self._run_deferred_gpu_capabilities_refresh(),
            name="gpu-tuning-capabilities-refresh",
            logger=self.logger,
            cancellation_id=create_system_id(
                subsystem="gpu_tuning_capabilities",
                owner="refresh",
                include_random_suffix=True,
            ),
            owner="gpu_tuning_capabilities_refresh",
            metadata={"event": "GPUCapabilitiesChangedEvent"},
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
        )

    async def _run_deferred_gpu_capabilities_refresh(self) -> bool:
        await asyncio.sleep(GPU_CAPABILITIES_REFRESH_DEBOUNCE_SECONDS)
        event_bus = self.event_bus
        if event_bus is None or not can_emit_events(event_bus, self.main_loop):
            return False
        return await refresh_capabilities_after_settings_change(
            executor=self.executor,
            gpu_services=self.gpu_services,
            enrich_gpu_capabilities=self.enrich_gpu_capabilities,
            event_bus=event_bus,
            main_loop=self.main_loop,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            logger=self.logger,
            probe_timeout_seconds=self.gpu_capabilities_probe_timeout_seconds,
        )

    async def list_gpu_slots(self, device_id: str | None = None) -> JSONDict:
        return await asyncio.to_thread(
            sync_list_gpu_slots,
            executor=self.executor,
            storage=self.storage,
            detailed_gpu_info=self.detailed_gpu_info,
            logger=self.logger,
            device_id=device_id,
            gpu_services=self.gpu_services,
        )

    async def preview_gpu_slot(self, device_id: str, slot: str | int) -> JSONDict:
        return await asyncio.to_thread(
            sync_preview_gpu_slot,
            executor=self.executor,
            storage=self.storage,
            detailed_gpu_info=self.detailed_gpu_info,
            logger=self.logger,
            device_id=device_id,
            slot=slot,
            gpu_services=self.gpu_services,
        )

    async def store_gpu_slot(
        self,
        device_id: str,
        slot: str | int,
        settings: Mapping[str, JSONValue],
        field_modes: Mapping[str, JSONValue] | None = None,
        apply_at_boot: bool | None = None,
    ) -> JSONDict:
        if self.runtime_flags.hardware_mutation_disabled:
            return hardware_mutation_disabled_payload()
        return await store_gpu_slot_with_lease(
            self,
            device_id,
            slot,
            settings,
            field_modes,
            apply_at_boot,
        )

    async def clear_gpu_slot(self, device_id: str, slot: str | int) -> JSONDict:
        return await clear_gpu_slot_with_lease(self, device_id, slot)

    async def toggle_gpu_slot_boot(
        self,
        device_id: str,
        slot: str | int,
        enabled: bool,
    ) -> JSONDict:
        if self.runtime_flags.hardware_mutation_disabled:
            return hardware_mutation_disabled_payload()
        return await toggle_gpu_slot_boot_with_lease(self, device_id, slot, enabled)

    async def apply_gpu_slot(
        self,
        device_id: str,
        slot: str | int,
        apply_at_boot: bool | None = None,
    ) -> JSONDict:
        if self.runtime_flags.hardware_mutation_disabled:
            return hardware_mutation_disabled_payload()
        return await apply_gpu_slot_with_lease(self, device_id, slot, apply_at_boot)

    async def apply_gpu_settings_direct(self, device_id: str, settings: JSONDict) -> JSONDict:
        if self.runtime_flags.hardware_mutation_disabled:
            return hardware_mutation_disabled_payload()
        return await apply_gpu_settings_direct_with_lease(self, device_id, settings)

    async def apply_gpu_settings_with_snapshots(
        self, device_id: str, settings: JSONDict, *, hardware_manager: HardwareManagerProtocol
    ) -> JSONDict:
        if self.runtime_flags.hardware_mutation_disabled:
            return hardware_mutation_disabled_control_response(device_id)
        return await apply_snapshot_gpu_controls(
            self.gpu_settings_apply_deps,
            self,
            hardware_manager,
            device_id=device_id,
            settings=settings,
        )

    async def apply_gpu_settings_direct_unlocked(
        self,
        device_id: str,
        settings: JSONDict,
    ) -> JSONDict:
        return await apply_gpu_settings_direct_for_service(self, device_id, settings)

    async def process_gpu_settings_request(
        self,
        payload: Mapping[str, JSONValue],
    ) -> GPUSettingsOutcome:
        if self.runtime_flags.hardware_mutation_disabled:
            return hardware_mutation_disabled_outcome()
        return await process_gpu_settings_request_with_lease(self, payload)

    def invalidate_gpu_caches(self) -> None:
        self.gpu_services.gpu_info_cache_service.invalidate_cache(
            owner="hardware.gpu_tuning", reason="control_sources_invalidated"
        )
        self.gpu_services.gpu_vendor_detection_service.invalidate_cache()
        self.gpu_services.nvidia_capabilities_cache_service.clear()

    async def apply_startup_gpu_settings(self) -> GPUControlStartupResult:
        if self.runtime_flags.hardware_mutation_disabled:
            return GPUControlStartupResult(
                GPUControlStartupDisposition.SKIPPED_POLICY_DISABLED, None
            )
        return await apply_startup_gpu_settings(
            settings_deps=self.gpu_settings_apply_deps,
            event_bus=self.event_bus,
            main_loop=self.main_loop,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            dirty_flag_path=self.dirty_flag_path,
        )

    async def clear_dirty_shutdown_flag(self, *, deadline_monotonic: float) -> None:
        if not await drain_control_operations(
            self.control_operation_state, deadline_monotonic=deadline_monotonic
        ):
            raise TimeoutError("GPU control workers remain owned at shutdown.")
        if self.gpu_services.adl_runtime is not None:
            self.gpu_services.adl_runtime.shutdown()
        self.native_control_recovery.require_clean_shutdown()
        await clear_dirty_shutdown_flag_file(self.dirty_flag_path, self.logger)
