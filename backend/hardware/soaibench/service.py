"""SoAI - SoAIBench public service [backend/hardware/soaibench/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from core.concurrency.locks import AsyncRWLock
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.soaibench_persistence import SoAIBenchMutationOutcome
from core.tasks.task_cancellation import mark_task_cancellation_requested
from core.timing.epoch import epoch_ms
from hardware.soaibench.active_runs import ActiveSoAIBenchRuns
from hardware.soaibench.dependencies import SoAIBenchServiceDependencies
from hardware.soaibench.errors import SoAIBenchRunningWithoutOwner, SoAIBenchUnsupported
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
    SoAIBenchProfile,
    SoAIBenchRunStatus,
)

STOP_EVENT_OPERATION = "hardware.soaibench.stop_event.publish"

if TYPE_CHECKING:
    from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallActivity
    from core.types.json import JSONDict

__all__ = (
    "SoAIBenchService",
    "SoAIBenchServiceDependencies",
)

SHUTDOWN_OPERATION = "hardware.soaibench.shutdown"
HISTORY_RESET_OPERATION = "hardware.soaibench.history_reset"
LOCAL_DELETION_EVENT_OPERATION = "hardware.soaibench.local_deletion_event"


class SoAIBenchService:
    def __init__(self, deps: SoAIBenchServiceDependencies) -> None:
        self._deps = deps
        self._active_runs = ActiveSoAIBenchRuns()
        self._history_reset_lock = AsyncRWLock()
        self._ready = asyncio.Event()
        self._reconcile_lock = asyncio.Lock()
        self._publication_service = deps.publication_service

    async def reconcile_startup(self) -> None:
        async with self._reconcile_lock:
            if self._ready.is_set():
                return
            self._active_runs.clear()
            await self._deps.activity_registry.clear()
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
                    device_id=device_id,
                    profile=parsed_profile,
                    benchmark_mode=parsed_mode,
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
            if run.get("status") != SoAIBenchRunStatus.RUNNING.value:
                await attach_existing_task_id(self._deps.task_registry, run)
                return run_response(run, accepted=False)
            active = self._active_runs.get(run_id)
            if active is None:
                refreshed = await self._deps.database_hardware.get_soaibench_run_for_user(
                    user_id=user_id,
                    run_id=run_id,
                )
                if refreshed is not None and refreshed.get("status") != "running":
                    await attach_existing_task_id(self._deps.task_registry, refreshed)
                    return run_response(refreshed, accepted=False)
                raise SoAIBenchRunningWithoutOwner(
                    "SoAIBench running run has no active worker owner.",
                )
            stop_result = await self._deps.database_hardware.request_soaibench_stop(
                user_id=user_id,
                run_id=run_id,
                stop_requested_at_ms=epoch_ms(),
            )
            stopped_run = stop_result.run
            if stopped_run is None:
                raise ValidationError("SoAIBench run was not found at stop mutation.")
            if stop_result.outcome == SoAIBenchMutationOutcome.ACCEPTED:
                try:
                    await publish_soaibench_run_update(
                        event_bus=self._deps.event_bus,
                        logger=self._deps.logger,
                        run=stopped_run,
                        update_type="stop_requested",
                        task_id=active.task_id,
                    )
                except HANDLED_RUNTIME_EXCEPTIONS as exception:
                    coerced_exception = coerce_to_soai_error(
                        exception,
                        operation=STOP_EVENT_OPERATION,
                    )
                    log_exception(
                        self._deps.logger,
                        coerced_exception,
                        message="SoAIBench stop-request publication failed.",
                        operation=STOP_EVENT_OPERATION,
                        details={"run_id": run_id, "task_id": active.task_id},
                        level="warning",
                    )
                finally:
                    active.stop_event.set()
                    await self._deps.opencl_pool.notify_waiters()
                    await mark_task_cancellation_requested(
                        self._deps.task_registry,
                        active.task_id,
                    )
            response_run = dict(stopped_run)
            response_run["task_id"] = active.task_id
            return run_response(
                response_run,
                accepted=stop_result.outcome == SoAIBenchMutationOutcome.ACCEPTED,
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

    async def delete_local_run(self, *, run_id: str, user_id: int) -> JSONDict:
        self._require_ready()
        async with self._history_reset_lock.write_lock():
            run = await self._deps.database_hardware.get_soaibench_run_for_user(
                user_id=user_id,
                run_id=run_id,
            )
            if run is None:
                raise ValidationError("SoAIBench run was not found.")
            await self._deps.database_hardware.delete_soaibench_local_run(
                run_id=run_id, user_id=user_id
            )
            try:
                await publish_soaibench_run_update(
                    event_bus=self._deps.event_bus,
                    logger=self._deps.logger,
                    run=run,
                    update_type="local_deleted",
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                coerced_exception = coerce_to_soai_error(
                    exception,
                    operation=LOCAL_DELETION_EVENT_OPERATION,
                )
                log_exception(
                    self._deps.logger,
                    coerced_exception,
                    message="SoAIBench local-deletion publication failed.",
                    operation=LOCAL_DELETION_EVENT_OPERATION,
                    details={"run_id": run_id},
                    level="warning",
                )
        return {"success": True, "run_id": run_id, "state": "local_history_deleted"}

    async def preview_publication(self, *, run_id: str, user_id: int) -> JSONDict:
        self._require_ready()
        async with self._history_reset_lock.read_lock():
            return await self._publication_service.preview(run_id=run_id, user_id=user_id)

    async def publish_run(self, *, run_id: str, user_id: int) -> tuple[int, JSONDict]:
        self._require_ready()
        async with self._history_reset_lock.read_lock():
            return await self._publication_service.publish(run_id=run_id, user_id=user_id)

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
