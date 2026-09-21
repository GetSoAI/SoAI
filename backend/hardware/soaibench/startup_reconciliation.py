"""SoAI - SoAIBench process-boundary reconciliation [backend/hardware/soaibench/startup_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.type_catalog import TASK_TYPE_HARDWARE_SOAIBENCH
from core.timing.epoch import epoch_ms
from core.tool_calls.status_values import is_active_tool_call_status
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from hardware.soaibench.responses import run_response
from hardware.soaibench.runtime import TASK_ID_PREFIX, task_id_for_run
from hardware.soaibench.terminal_projection import terminal_projection

if TYPE_CHECKING:
    from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.tasks.task import Task
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict

__all__ = ("reconcile_soaibench_process_boundary",)

TASK_PAGE_SIZE = 1000
TOOL_CALL_PAGE_SIZE = 100


async def reconcile_soaibench_process_boundary(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    task_queries: TaskRegistryQueryView,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
) -> None:
    reconciliation = await database_hardware.reconcile_soaibench_running_rows(epoch_ms())
    affected_by_task_id = {task_id_for_run(str(run["run_id"])): run for run in reconciliation.runs}
    seen_task_ids: set[str] = set()
    after_created_at_ms = 0
    after_task_id = ""
    while True:
        tasks = await task_queries.query_active_by_type_keyset(
            TASK_TYPE_HARDWARE_SOAIBENCH,
            after_created_at_ms=after_created_at_ms,
            after_task_id=after_task_id,
            limit=TASK_PAGE_SIZE,
        )
        if not tasks:
            break
        for task in tasks:
            await _reconcile_active_task(
                database_hardware=database_hardware,
                task_registry=task_registry,
                database_tool_calls=database_tool_calls,
                task=task,
                logger=logger,
            )
            seen_task_ids.add(task.task_id)
        last_task = tasks[-1]
        after_created_at_ms = last_task.created_at_ms
        after_task_id = last_task.task_id
        if len(tasks) < TASK_PAGE_SIZE:
            break
    for task_id, run in affected_by_task_id.items():
        if task_id in seen_task_ids:
            continue
        affected_task = await task_registry.get(task_id, force_refresh=True)
        if affected_task is None:
            await _reconcile_tool_call(
                database_tool_calls,
                task_id,
                run,
                logger=logger,
            )
        elif not affected_task.status.is_terminal():
            await _finalize_task_and_tool(
                task_registry=task_registry,
                database_tool_calls=database_tool_calls,
                task=affected_task,
                run=run,
                logger=logger,
            )
        else:
            _diagnose_terminal_task_conflict(affected_task, run, logger=logger)
            await _reconcile_tool_call(
                database_tool_calls,
                task_id,
                run,
                logger=logger,
            )
    await _reconcile_remaining_active_tool_calls(
        database_hardware=database_hardware,
        task_registry=task_registry,
        database_tool_calls=database_tool_calls,
        logger=logger,
        reconciled_task_ids=seen_task_ids,
    )


async def _reconcile_remaining_active_tool_calls(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
    reconciled_task_ids: set[str],
) -> None:
    after_storage_call_id = ""
    while True:
        page = await database_tool_calls.list_active_tool_calls_by_owner_task_prefix(
            owner_task_prefix=TASK_ID_PREFIX,
            after_storage_call_id=after_storage_call_id,
            limit=TOOL_CALL_PAGE_SIZE,
        )
        for tool_call in page:
            task_id = str(tool_call.get("owner_task_id") or "").strip()
            if not task_id or task_id in reconciled_task_ids:
                continue
            task = await task_registry.get(task_id, force_refresh=True)
            if task is None or task.task_type != TASK_TYPE_HARDWARE_SOAIBENCH:
                raise StateError("SoAIBench deferred tool call has no matching task owner.")
            run_id_value = task.metadata.get("run_id")
            if not isinstance(run_id_value, str) or task_id != task_id_for_run(run_id_value):
                raise StateError("SoAIBench deferred tool call task identity is invalid.")
            run = await database_hardware.get_soaibench_run_for_user(
                user_id=task.user_id,
                run_id=run_id_value,
            )
            if run is None or run.get("status") == "running":
                raise StateError("SoAIBench deferred tool call has no terminal durable run.")
            await _reconcile_tool_call(
                database_tool_calls,
                task_id,
                run,
                logger=logger,
            )
            reconciled_task_ids.add(task_id)
        if len(page) < TOOL_CALL_PAGE_SIZE:
            break
        after_storage_call_id = str(page[-1]["id"])


async def _reconcile_active_task(
    *,
    database_hardware: DatabaseSoAIBenchProtocol,
    task_registry: TaskRegistryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task: Task,
    logger: LoggerProtocol,
) -> None:
    run_id_value = task.metadata.get("run_id")
    if not isinstance(run_id_value, str) or not run_id_value.strip():
        _diagnose_missing_run(task, None, "missing_run_id", logger=logger)
        await _finalize_missing_run_task(task_registry, task, "missing_run_id")
        return
    run_id = run_id_value.strip()
    if task.task_id != task_id_for_run(run_id):
        raise StateError("SoAIBench task identity does not match its persisted run_id.")
    run = await database_hardware.get_soaibench_run_for_user(
        user_id=task.user_id,
        run_id=run_id,
    )
    if run is None:
        _diagnose_missing_run(task, run_id, "missing_run", logger=logger)
        await _finalize_missing_run_task(task_registry, task, "missing_run")
        return
    if run.get("status") == "running":
        raise StateError("SoAIBench run remained running after process-boundary reconciliation.")
    await _finalize_task_and_tool(
        task_registry=task_registry,
        database_tool_calls=database_tool_calls,
        task=task,
        run=run,
        logger=logger,
    )


async def _finalize_missing_run_task(
    task_registry: TaskRegistryProtocol,
    task: Task,
    reason: str,
) -> None:
    await finalize(
        task_registry,
        task.task_id,
        TaskStatus.FAILED,
        prefetched_task=task,
        result={"status": "failed", "reason": reason},
        error_message="SoAIBench durable run is missing.",
    )


def _diagnose_missing_run(
    task: Task,
    run_id: str | None,
    reason: str,
    *,
    logger: LoggerProtocol,
) -> None:
    logger.warning(
        "SoAIBench active task references invalid or missing durable run state.",
        extra={
            "soai_integrity": {
                "task_id": task.task_id,
                "run_id": run_id,
                "reason": reason,
            },
        },
    )


async def _finalize_task_and_tool(
    *,
    task_registry: TaskRegistryProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task: Task,
    run: JSONDict,
    logger: LoggerProtocol,
) -> None:
    projection = terminal_projection(run)
    await finalize(
        task_registry,
        task.task_id,
        projection.task_status,
        prefetched_task=task,
        result=projection.task_result,
        error_message=projection.error_message,
        status_message=projection.status_message,
    )
    await _reconcile_tool_call(
        database_tool_calls,
        task.task_id,
        run,
        logger=logger,
    )


async def _reconcile_tool_call(
    database_tool_calls: DatabaseToolCallsProtocol,
    task_id: str,
    run: JSONDict,
    *,
    logger: LoggerProtocol,
) -> None:
    owner_calls: list[JSONDict] = []
    after_storage_call_id = ""
    while True:
        page = await database_tool_calls.list_tool_calls_by_owner_task(
            owner_task_id=task_id,
            after_storage_call_id=after_storage_call_id,
            limit=TOOL_CALL_PAGE_SIZE,
        )
        owner_calls.extend(page)
        if len(page) < TOOL_CALL_PAGE_SIZE:
            break
        after_storage_call_id = str(page[-1]["id"])
    active_calls = [
        tool_call
        for tool_call in owner_calls
        if is_active_tool_call_status(str(tool_call.get("status") or ""))
    ]
    if len(active_calls) > 1:
        raise StateError("SoAIBench task owns more than one active deferred tool call.")
    if not owner_calls:
        return
    projection = terminal_projection(run)
    for tool_call in owner_calls:
        tool_status = str(tool_call.get("status") or "")
        if is_active_tool_call_status(tool_status) or tool_status == projection.tool_status:
            continue
        logger.warning(
            "SoAIBench terminal tool call conflicts with its durable run.",
            extra={
                "soai_integrity": {
                    "run_id": str(run["run_id"]),
                    "task_id": task_id,
                    "tool_call_id": str(tool_call["id"]),
                    "run_projection": projection.tool_status,
                    "tool_status": tool_status,
                },
            },
        )
    if not active_calls:
        return
    tool_call = active_calls[0]
    completed_at_ms = coerce_optional_non_negative_int_strict(run.get("completed_at_ms"))
    if completed_at_ms is None:
        raise StateError("SoAIBench terminal run is missing completed_at_ms.")
    duration_ms = coerce_optional_non_negative_int_strict(run.get("duration_ms")) or 0
    result_run = dict(run)
    result_run["task_id"] = task_id
    finalized = await database_tool_calls.finalize_active_tool_call_with_result(
        str(tool_call["id"]),
        status=projection.tool_status,
        tool_result=serialize_json_compact_stable(run_response(result_run, accepted=False)),
        error_message=projection.tool_error_message,
        duration_ms=duration_ms,
        completed_at_ms=completed_at_ms,
    )
    if finalized is None or finalized.get("status") != projection.tool_status:
        raise StateError("SoAIBench deferred tool call repair did not reach terminal state.")


def _diagnose_terminal_task_conflict(
    task: Task,
    run: JSONDict,
    *,
    logger: LoggerProtocol,
) -> None:
    projection = terminal_projection(run)
    if task.status == projection.task_status:
        return
    logger.warning(
        "SoAIBench terminal task conflicts with its durable run.",
        extra={
            "soai_integrity": {
                "run_id": str(run["run_id"]),
                "task_id": task.task_id,
                "run_projection": projection.task_status.value,
                "task_status": task.status.value,
            },
        },
    )
