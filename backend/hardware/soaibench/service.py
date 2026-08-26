"""SoAI - SoAIBench V1 public service [backend/hardware/soaibench/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from core.concurrency.locks import AsyncRWLock
from core.errors.exceptions import ValidationError
from core.tasks.task_cancellation import mark_task_cancellation_requested
from core.timing.epoch import epoch_ms
from hardware.soaibench.active_runs import ActiveSoAIBenchRuns
from hardware.soaibench.dependencies import SoAIBenchServiceDependencies
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.events import publish_soaibench_run_update
from hardware.soaibench.gpu_identity import (
    identity_payload_for_history,
    resolve_gpu_identity,
)
from hardware.soaibench.history_service import (
    export_soaibench_history_csv,
    list_soaibench_history,
    list_soaibench_runs,
)
from hardware.soaibench.responses import run_response
from hardware.soaibench.runtime import (
    parse_benchmark_mode,
    parse_profile,
    parse_temperature_limit_celsius,
)
from hardware.soaibench.service_cancellation import cancel_active_soaibench_runs
from hardware.soaibench.service_support import unsupported_response
from hardware.soaibench.start_flow import start_soaibench_run
from hardware.soaibench.task_identity import attach_existing_task_id
from hardware.soaibench.types import (
    SoAIBenchBenchmarkMode,
    SoAIBenchGpuIdentity,
    SoAIBenchProfile,
    SoAIBenchRunStatus,
)

if TYPE_CHECKING:
    from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallActivity
    from core.types.json import JSONDict

__all__ = (
    "SoAIBenchService",
    "SoAIBenchServiceDependencies",
)

SHUTDOWN_OPERATION = "hardware.soaibench.shutdown"
HISTORY_RESET_OPERATION = "hardware.soaibench.history_reset"


class SoAIBenchService:
    def __init__(self, deps: SoAIBenchServiceDependencies) -> None:
        self._deps = deps
        self._active_runs = ActiveSoAIBenchRuns()
        self._history_reset_lock = AsyncRWLock()
        self._ready = asyncio.Event()

    async def reconcile_startup(self) -> None:
        self._active_runs.clear()
        await self._deps.activity_registry.clear()
        await self._deps.database_hardware.reconcile_soaibench_running_rows(epoch_ms())
        self._ready.set()

    async def shutdown(self) -> None:
        try:
            async with self._history_reset_lock.write_lock():
                await cancel_active_soaibench_runs(
                    deps=self._deps,
                    active_runs=self._active_runs,
                    reason="SoAIBench backend shutdown",
                    operation=SHUTDOWN_OPERATION,
                    cancelled_message="SoAIBench worker cancelled during shutdown.",
                )
        finally:
            await self._deps.opencl_pool.shutdown()

    async def reset_history(self) -> None:
        self._require_ready()
        async with self._history_reset_lock.write_lock():
            await cancel_active_soaibench_runs(
                deps=self._deps,
                active_runs=self._active_runs,
                reason="SoAIBench history reset",
                operation=HISTORY_RESET_OPERATION,
                cancelled_message="SoAIBench worker cancelled during history reset.",
            )
            await self._deps.database_hardware.clear_hardware_history()

    async def start_run(
        self,
        *,
        device_id: str,
        profile: str,
        created_by_user_id: int,
        created_by_tool: str,
        benchmark_mode: str | None = None,
        temperature_limit_celsius: float | None = None,
        deferred_tool_activity: DeferredToolCallActivity | None = None,
    ) -> JSONDict:
        parsed_profile = parse_profile(profile)
        parsed_mode = parse_benchmark_mode(benchmark_mode)
        parsed_temperature_limit = parse_temperature_limit_celsius(temperature_limit_celsius)
        if (
            parsed_mode == SoAIBenchBenchmarkMode.CERTIFIED
            and parsed_profile != SoAIBenchProfile.STANDARD
        ):
            raise ValidationError("certified benchmark_mode requires standard profile.")
        if not self._deps.hardware_manager.enabled:
            return unsupported_response(
                device_id=device_id,
                profile=parsed_profile.value,
                reason="hardware_manager_unavailable",
                message="Hardware manager is disabled.",
            )
        self._require_ready()
        async with self._history_reset_lock.read_lock():
            try:
                response = await start_soaibench_run(
                    deps=self._deps,
                    active_runs=self._active_runs,
                    resolve_identity=self._resolve_identity,
                    device_id=device_id,
                    profile=parsed_profile.value,
                    benchmark_mode=parsed_mode.value,
                    created_by_user_id=created_by_user_id,
                    created_by_tool=created_by_tool,
                    temperature_limit_celsius=parsed_temperature_limit,
                    deferred_tool_activity=deferred_tool_activity,
                )
            except SoAIBenchUnsupported as exception:
                response = unsupported_response(
                    device_id=device_id,
                    profile=parsed_profile.value,
                    reason=exception.reason,
                    message=exception.message,
                )
        return response

    async def get_run(self, *, run_id: str, user_id: int) -> JSONDict:
        async with self._history_reset_lock.read_lock():
            run = await self._deps.database_hardware.get_soaibench_run_for_user(
                user_id=user_id,
                run_id=run_id,
            )
            if run is None:
                raise ValidationError("SoAIBench run was not found.")
            await attach_existing_task_id(self._deps.task_registry, run)
            return run_response(
                run,
                accepted=run.get("status") == SoAIBenchRunStatus.RUNNING.value,
            )

    async def stop_run(self, *, run_id: str, user_id: int) -> JSONDict:
        async with self._history_reset_lock.read_lock():
            run = await self._deps.database_hardware.get_soaibench_run_for_user(
                user_id=user_id,
                run_id=run_id,
            )
            if run is None:
                raise ValidationError("SoAIBench run was not found.")
            active = self._active_runs.get(run_id)
            if active is None:
                raise ValidationError("soaibench_stop_not_active")
            active.stop_event.set()
            persisted_stop_request = await self._deps.database_hardware.request_soaibench_stop(
                run_id=run_id,
                stop_requested_at_ms=epoch_ms(),
            )
            if persisted_stop_request:
                await publish_soaibench_run_update(
                    database_hardware=self._deps.database_hardware,
                    event_bus=self._deps.event_bus,
                    logger=self._deps.logger,
                    user_id=user_id,
                    run_id=run_id,
                    update_type="stop_requested",
                    task_id=active.task_id,
                )
            await mark_task_cancellation_requested(self._deps.task_registry, active.task_id)
            refreshed = await self._deps.database_hardware.get_soaibench_run_for_user(
                user_id=user_id,
                run_id=run_id,
            )
            if refreshed is None:
                raise ValidationError("SoAIBench run was not found after stop request.")
            if (
                refreshed.get("status") == SoAIBenchRunStatus.RUNNING.value
                and refreshed.get("stop_requested_at_ms") is None
            ):
                raise ValidationError("SoAIBench stop request was not persisted.")
            refreshed["task_id"] = active.task_id
            return run_response(
                refreshed,
                accepted=refreshed.get("status") == SoAIBenchRunStatus.RUNNING.value,
            )

    async def list_history(self, *, device_id: str, user_id: int, limit: int) -> JSONDict:
        return await list_soaibench_history(
            deps=self._deps,
            history_reset_lock=self._history_reset_lock,
            resolve_identity_payload=self._resolve_history_identity_payload,
            device_id=device_id,
            user_id=user_id,
            limit=limit,
        )

    async def export_history_csv(
        self,
        *,
        device_id: str,
        user_id: int,
    ) -> tuple[str, AsyncIterator[bytes]]:
        return await export_soaibench_history_csv(
            deps=self._deps,
            history_reset_lock=self._history_reset_lock,
            resolve_identity_payload=self._resolve_history_identity_payload,
            device_id=device_id,
            user_id=user_id,
        )

    async def list_runs(self, *, user_id: int, limit: int) -> JSONDict:
        return await list_soaibench_runs(
            deps=self._deps,
            history_reset_lock=self._history_reset_lock,
            user_id=user_id,
            limit=limit,
        )

    async def _resolve_identity(self, device_id: str) -> SoAIBenchGpuIdentity:
        if not self._deps.hardware_manager.enabled:
            raise SoAIBenchUnsupported(
                reason="hardware_manager_unavailable",
                message="Hardware manager is disabled.",
            )
        snapshot = await self._gpu_snapshot()
        try:
            return resolve_gpu_identity(snapshot, device_id)
        except ValidationError as exception:
            raise SoAIBenchUnsupported(
                reason="gpu_inventory_unavailable",
                message=str(exception),
            ) from exception

    async def _resolve_history_identity_payload(self, device_id: str) -> JSONDict:
        if not self._deps.hardware_manager.enabled:
            raise SoAIBenchUnsupported(
                reason="hardware_manager_unavailable",
                message="Hardware manager is disabled.",
            )
        snapshot = await self._gpu_snapshot()
        try:
            identity = resolve_gpu_identity(snapshot, device_id)
        except ValidationError as exception:
            raise SoAIBenchUnsupported(
                reason="gpu_inventory_unavailable",
                message=str(exception),
            ) from exception
        return identity_payload_for_history(snapshot, identity)

    async def _gpu_snapshot(self) -> JSONDict:
        return await self._deps.hardware_manager.get_system_info(["gpu"], cache=False)

    def _require_ready(self) -> None:
        if self._ready.is_set():
            return
        raise ValidationError("SoAIBench startup reconciliation has not completed.")
