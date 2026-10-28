"""SoAI - Owned concurrent system capability acquisition [backend/hardware/manager/system_capability_acquisition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.bounded_blocking import run_bounded_blocking_call
from core.concurrency.cancellation_cleanup import run_idempotent_current_task_operation
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import StateError
from core.hardware.gpu_inventory_errors import GPUObservationSupersededError
from core.logging.protocols import TraceLogger
from hardware.manager.system_capabilities import sync_get_system_capabilities

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.cpu_rapl import RaplEnergyCache
    from hardware.manager.dependencies import HardwareManagerDependencies
    from hardware.manager.manager_state import HardwareManagerState

__all__ = ("acquire_system_capabilities", "shutdown_system_capability_acquisition")


async def acquire_system_capabilities(
    *,
    state: HardwareManagerState,
    dependencies: HardwareManagerDependencies,
    logger: TraceLogger,
    history_enabled: bool,
    rapl_energy_cache: RaplEnergyCache,
) -> JSONDict:
    generation = state.system_capability_generation

    def acquire_current_revision(revision: int) -> JSONDict:
        if state.system_capability_stopping or generation != state.system_capability_generation:
            raise StateError("System capability acquisition is stopping.")
        if revision != dependencies.gpu_info_cache_service.revision():
            raise GPUObservationSupersededError("System capability acquisition was superseded.")
        return sync_get_system_capabilities(
            executor=dependencies.command_executor,
            logger=logger,
            monitoring_interval_ms=dependencies.settings.monitoring_interval_ms,
            history_config=dependencies.settings.history_config,
            history_enabled=history_enabled,
            gpu_info_cache_service=dependencies.gpu_info_cache_service,
            gpu_vendor_detection_service=dependencies.gpu_vendor_detection_service,
            nvidia_nvml_gate=dependencies.nvidia_nvml_gate,
            nvidia_capabilities_cache_service=dependencies.nvidia_capabilities_cache_service,
            rapl_energy_cache=rapl_energy_cache,
            adl_runtime=dependencies.adl_runtime,
        )

    async def compute(revision: int) -> JSONDict:
        if state.system_capability_stopping or generation != state.system_capability_generation:
            raise StateError("System capability acquisition is stopping.")
        state.system_capability_acquisitions += 1
        state.system_capability_idle.clear()
        try:
            if state.system_capability_pool is None:
                state.system_capability_pool = dependencies.system_capability_pool_factory()
            result = await run_bounded_blocking_call(
                state.system_capability_pool,
                acquire_current_revision,
                revision,
            )
            if state.system_capability_stopping or generation != state.system_capability_generation:
                raise StateError("System capability acquisition was retired during shutdown.")
            if revision != dependencies.gpu_info_cache_service.revision():
                raise GPUObservationSupersededError("System capability acquisition was superseded.")
            return result
        finally:
            state.system_capability_acquisitions -= 1
            if state.system_capability_acquisitions == 0:
                state.system_capability_idle.set()

    for _attempt in range(3):
        revision = dependencies.gpu_info_cache_service.revision()

        try:
            return await state.system_capability_singleflight.execute_or_wait(
                (generation, revision), partial(compute, revision)
            )
        except GPUObservationSupersededError:
            continue
    raise GPUObservationSupersededError("System capability acquisition changed repeatedly.")


async def shutdown_system_capability_acquisition(state: HardwareManagerState) -> None:
    state.system_capability_stopping = True
    state.system_capability_generation += 1

    async def close_pool() -> None:
        if state.system_capability_acquisitions:
            await state.system_capability_idle.wait()
        pool = state.system_capability_pool
        if pool is not None:
            await run_joined_thread_call(
                partial(pool.executor.shutdown, wait=True, cancel_futures=False),
                task_name="hardware-system-capability-shutdown",
                retain_resources_until_complete=True,
            )
            state.system_capability_pool = None

    await run_idempotent_current_task_operation(close_pool)
