"""SoAI - Task cancellation command helpers [backend/core/tasks/cancellation_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_tasks import CancelTaskCommand
from core.logging.trace import get_context_trace_id, get_logger
from core.tasks.cancellation_ids import normalize_cancellation_id
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationHistoryProtocol,
)

__all__ = (
    "cancel_via_registry",
    "extract_cancel_command",
)

LOGGER_NAME = "SoAI.core.tasks.cancellation_commands"
OPERATION = "event_types.cancel_via_registry"


def extract_cancel_command(command: CancelTaskCommand) -> tuple[str, str] | None:
    try:
        cancellation_id = command.cancellation_id
    except AttributeError:
        cancellation_id = None
    if not cancellation_id:
        return None
    normalized_id = normalize_cancellation_id(cancellation_id)
    if not normalized_id:
        return None
    try:
        reason = command.reason
    except AttributeError:
        reason = None
    if not reason:
        reason = "Task cancelled"
    return (normalized_id, reason)


async def cancel_via_registry(
    command: CancelTaskCommand,
    cancellation_coordinator: CancellationCoordinatorProtocol,
    cancellation_history: CancellationHistoryProtocol,
) -> tuple[str, str] | None:
    logger = get_logger(LOGGER_NAME)
    cancel_args = extract_cancel_command(command)
    if not cancel_args:
        return None
    cancellation_id, reason = cancel_args
    try:
        if await cancellation_history.is_cancelled(cancellation_id):
            stored_reason = await cancellation_history.get_reason(cancellation_id)
            if stored_reason is not None and stored_reason.strip():
                return (cancellation_id, stored_reason.strip())
            return cancel_args
    except RECOVERABLE_EXCEPTIONS as exception:
        try:
            context = command.context
        except AttributeError:
            trace_id = None
        else:
            trace_id = get_context_trace_id(context)
        log_handled_exception(
            logger,
            exception,
            message="Cancellation check failed (non-critical).",
            trace_id=trace_id,
            operation=OPERATION,
            details={"cancellation_id": cancellation_id},
            level="debug",
        )
    await cancellation_coordinator.cancel_scope(cancellation_id, reason)
    return cancel_args
