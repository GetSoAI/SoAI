"""SoAI - SoAIBench history listing and CSV export service flows [backend/hardware/soaibench/history_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.soaibench_export import (
    build_soaibench_history_filename,
    iter_soaibench_history_csv_bytes,
)
from core.hardware.soaibench_limits import (
    SOAIBENCH_HISTORY_DEFAULT_LIMIT,
    SOAIBENCH_RUNS_DEFAULT_LIMIT,
)
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.events import publish_soaibench_run_update
from hardware.soaibench.responses import run_response
from hardware.soaibench.service_support import limit_or_default, unsupported_response
from hardware.soaibench.task_identity import attach_existing_task_ids

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from core.concurrency.locks import AsyncRWLock
    from core.types.json import JSONDict
    from hardware.soaibench.dependencies import SoAIBenchServiceDependencies

__all__ = (
    "delete_soaibench_local_run",
    "export_soaibench_history_csv",
    "list_soaibench_history",
    "list_soaibench_runs",
)


async def list_soaibench_history(
    *,
    deps: SoAIBenchServiceDependencies,
    history_reset_lock: AsyncRWLock,
    resolve_identity_payload: Callable[[str], Awaitable[JSONDict]],
    device_id: str,
    user_id: int,
    limit: int,
) -> JSONDict:
    if not deps.hardware_manager.enabled:
        return unsupported_response(
            device_id=device_id,
            profile=None,
            reason="hardware_manager_unavailable",
            message="Hardware manager is disabled.",
        )
    try:
        identity = await resolve_identity_payload(device_id)
    except SoAIBenchUnsupported as exception:
        return unsupported_response(
            device_id=device_id,
            profile=None,
            reason=exception.reason,
            message=exception.message,
        )
    async with history_reset_lock.read_lock():
        history = await deps.database_hardware.list_soaibench_history(
            user_id=user_id,
            identity=identity,
            limit=limit_or_default(limit, default=SOAIBENCH_HISTORY_DEFAULT_LIMIT),
        )
        await attach_existing_task_ids(deps.task_registry, history)
        latest: JSONDict = (
            history[0] if history else {"device_id": device_id, "status": "indeterminate"}
        )
        return run_response(latest, accepted=False, history=history)


async def export_soaibench_history_csv(
    *,
    deps: SoAIBenchServiceDependencies,
    history_reset_lock: AsyncRWLock,
    resolve_identity_payload: Callable[[str], Awaitable[JSONDict]],
    device_id: str,
    user_id: int,
) -> tuple[str, AsyncIterator[bytes]]:
    if not deps.hardware_manager.enabled:
        raise ValidationError("Hardware manager is disabled.")
    try:
        identity = await resolve_identity_payload(device_id)
    except SoAIBenchUnsupported as exception:
        raise ValidationError(exception.message) from exception
    async with history_reset_lock.read_lock():
        history = await deps.database_hardware.list_soaibench_history_export(
            user_id=user_id,
            identity=identity,
        )
    return build_soaibench_history_filename(), iter_soaibench_history_csv_bytes(history)


async def list_soaibench_runs(
    *,
    deps: SoAIBenchServiceDependencies,
    history_reset_lock: AsyncRWLock,
    user_id: int,
    limit: int,
) -> JSONDict:
    async with history_reset_lock.read_lock():
        runs = await deps.database_hardware.list_soaibench_recent_for_user(
            user_id=user_id,
            limit=limit_or_default(limit, default=SOAIBENCH_RUNS_DEFAULT_LIMIT),
        )
        await attach_existing_task_ids(deps.task_registry, runs)
        return {
            "success": True,
            "runs": [run_response(run, accepted=run.get("status") == "running") for run in runs],
        }


LOCAL_DELETION_EVENT_OPERATION = "hardware.soaibench.local_deletion_event"


async def delete_soaibench_local_run(
    *,
    deps: SoAIBenchServiceDependencies,
    history_reset_lock: AsyncRWLock,
    run_id: str,
    user_id: int,
) -> JSONDict:
    async with history_reset_lock.write_lock():
        run = await deps.database_hardware.get_soaibench_run_for_user(
            user_id=user_id,
            run_id=run_id,
        )
        if run is None:
            raise ValidationError("SoAI Bench run was not found.")
        await deps.database_hardware.delete_soaibench_local_run(run_id=run_id, user_id=user_id)
        try:
            await publish_soaibench_run_update(
                event_bus=deps.event_bus,
                logger=deps.logger,
                run=run,
                update_type="local_deleted",
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced_exception = coerce_to_soai_error(
                exception,
                operation=LOCAL_DELETION_EVENT_OPERATION,
            )
            log_exception(
                deps.logger,
                coerced_exception,
                message="SoAI Bench local-deletion publication failed.",
                operation=LOCAL_DELETION_EVENT_OPERATION,
                details={"run_id": run_id},
                level="warning",
            )
    return {"success": True, "run_id": run_id, "state": "local_history_deleted"}
