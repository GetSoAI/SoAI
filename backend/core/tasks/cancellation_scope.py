"""SoAI - Cancellation scope publication and verification [backend/core/tasks/cancellation_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tasks.cancellation import publish_cancel

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import (
        CancellationCoordinatorProtocol,
        CancellationHistoryProtocol,
    )
    from core.types.json import JSONDict

__all__ = ("publish_and_verify_cancellation_scope_noncritical",)

OPERATION_CANCELLATION_SCOPE = "task.cancellation_scope.publish_and_verify"


async def publish_and_verify_cancellation_scope_noncritical(
    *,
    event_bus: EventBusProtocol,
    cancellation_coordinator: CancellationCoordinatorProtocol,
    cancellation_history: CancellationHistoryProtocol,
    context: RequestContext,
    reason: str,
    cancellation_id: str,
    logger: LoggerProtocol,
    publish_message: str,
    verify_message: str,
    level: Literal["debug", "info", "warning", "error", "critical"],
    details: JSONDict,
) -> bool:
    try:
        await publish_cancel(
            event_bus,
            cancellation_coordinator,
            cancellation_history,
            context,
            reason,
            cancellation_id=cancellation_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=publish_message,
            trace_id=context.trace_id,
            operation=OPERATION_CANCELLATION_SCOPE,
            level=level,
            details=details,
        )
        return False
    try:
        return await cancellation_history.is_cancelled(cancellation_id)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=verify_message,
            trace_id=context.trace_id,
            operation=OPERATION_CANCELLATION_SCOPE,
            level=level,
            details=details,
        )
        return False
