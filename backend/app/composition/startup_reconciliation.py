"""SoAI - Startup reconciliation entrypoints for app composition [backend/app/composition/startup_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.updater.software_update.activation_state import find_pending_update_activation
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from core.tasks.recovery import reconcile_stale_active_tasks_on_startup
from core.tasks.software_update_result import reconcile_software_update_result
from core.tasks.type_catalog import (
    TASK_TYPE_RAG_DOCUMENT_UPLOAD,
    TASK_TYPE_RAG_REINDEX,
    TASK_TYPE_RAG_WEB_FETCH_INGEST,
)
from core.timing.epoch import epoch_ms
from features.agent.runtime.process_boundary_turn_reconciliation import (
    ProcessBoundaryMode,
    reconcile_turns_at_process_boundary,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import (
        DatabaseAgentTurnProcessBoundaryProtocol,
        DatabaseAgentTurnsProtocol,
    )
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = (
    "reconcile_agent_turns_on_startup",
    "reconcile_task_registry",
)

OPERATION_RECONCILE_AGENT_TURNS_STARTUP = "app.composition.reconcile_agent_turns_on_startup"
OPERATION_RECONCILE_TASK_REGISTRY = "app.composition.reconcile_task_registry"
_RAG_DOCUMENT_TASK_TYPES = frozenset(
    (
        TASK_TYPE_RAG_DOCUMENT_UPLOAD,
        TASK_TYPE_RAG_WEB_FETCH_INGEST,
    ),
)


async def reconcile_task_registry(
    *,
    task_registry: TaskRegistryProtocol,
    logger: LoggerProtocol,
    base_path: str,
) -> None:
    operation_failures: list[SoAIError] = []
    reconciled_update = False
    pending_activation = find_pending_update_activation(base_path)
    try:
        if pending_activation is None:
            reconciled_update = await reconcile_software_update_result(
                task_registry,
                base_path=base_path,
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        operation_failures.append(
            coerce_to_soai_error(
                exception,
                operation=OPERATION_RECONCILE_TASK_REGISTRY,
            )
        )
    stale_result = None
    try:
        stale_result = await reconcile_stale_active_tasks_on_startup(
            task_registry,
            started_at_epoch_ms=epoch_ms(),
            exclude_task_ids=(
                (pending_activation.task_id,) if pending_activation is not None else ()
            ),
            exclude_task_types=tuple(
                sorted(_RAG_DOCUMENT_TASK_TYPES | {TASK_TYPE_RAG_REINDEX}),
            ),
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        operation_failures.append(
            coerce_to_soai_error(
                exception,
                operation=OPERATION_RECONCILE_TASK_REGISTRY,
            )
        )
    reconciled_responses = 0
    try:
        reconciled_responses = (
            await task_registry.database_tasks.reconcile_terminal_background_responses()
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        operation_failures.append(
            coerce_to_soai_error(
                exception,
                operation=OPERATION_RECONCILE_TASK_REGISTRY,
            )
        )
    if stale_result is not None and stale_result.finalized_count:
        logger.warning(
            "Reconciled %d stale active task(s) after startup.",
            stale_result.finalized_count,
        )
    if reconciled_responses:
        logger.warning(
            "Reconciled %d terminal background response(s) after startup.",
            reconciled_responses,
        )
    if reconciled_update:
        logger.info("Reconciled the durable software update result after startup.")
    stale_failures = stale_result.failures if stale_result is not None else ()
    if not stale_failures and not operation_failures:
        return
    failure_details = [
        {"task_id": failure.task_id, "error_code": str(failure.error.code)}
        for failure in stale_failures[:50]
    ]
    first_error = stale_failures[0].error if stale_failures else operation_failures[0]
    raise StateError(
        "Task startup reconciliation completed with failures.",
        operation=OPERATION_RECONCILE_TASK_REGISTRY,
        details={
            "stale_task_failure_count": len(stale_failures),
            "operation_failure_count": len(operation_failures),
            "operation_failure_codes": [str(error.code) for error in operation_failures[:10]],
            "stale_task_failures": failure_details,
        },
        cause=first_error,
    )


async def reconcile_agent_turns_on_startup(
    *,
    database_agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
) -> None:
    try:
        reconciled = await reconcile_turns_at_process_boundary(
            database_agent_turn_process_boundary=database_agent_turn_process_boundary,
            database_agent_turns=database_agent_turns,
            database_tool_calls=database_tool_calls,
            mode=ProcessBoundaryMode.STARTUP,
        )
        if reconciled:
            logger.warning("Reconciled %d stale agent turn(s) from previous boot.", reconciled)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Agent turn startup reconciliation failed",
            operation=OPERATION_RECONCILE_AGENT_TURNS_STARTUP,
            level="warning",
        )
    except SoAIError as exception:
        log_exception(
            logger,
            exception,
            message="Agent turn startup reconciliation failed",
            operation=OPERATION_RECONCILE_AGENT_TURNS_STARTUP,
            level="warning",
        )
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_RECONCILE_AGENT_TURNS_STARTUP,
        )
        log_exception(
            logger,
            coerced,
            message="Unexpected agent turn startup reconciliation failure",
            operation=OPERATION_RECONCILE_AGENT_TURNS_STARTUP,
            level="warning",
        )
