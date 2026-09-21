"""SoAI - Noncritical task finalization boundary [backend/core/tasks/noncritical_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ApiError, SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tasks.task import Task
    from core.types.json import JSONValue

__all__ = ("finalize_noncritical",)


async def finalize_noncritical(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    status: TaskStatus,
    *,
    result: Mapping[str, JSONValue] | None = None,
    error_code: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    status_message: str | None = None,
    emit_reply_completion_event: bool = True,
    logger: LoggerProtocol,
    operation: str,
    log_message: str,
    details: Mapping[str, JSONValue],
) -> Task | None:
    try:
        return await finalize(
            registry,
            task_id,
            status,
            result=result,
            error_code=error_code,
            error_type=error_type,
            error_message=error_message,
            status_message=status_message,
            emit_reply_completion_event=emit_reply_completion_event,
        )
    except ApiError:
        raise
    except SoAIError as exception:
        log_exception(
            logger,
            exception,
            message=log_message,
            operation=operation,
            details=dict(details),
        )
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            logger,
            coerced,
            message=log_message,
            operation=operation,
            details=dict(details),
        )
        return None
