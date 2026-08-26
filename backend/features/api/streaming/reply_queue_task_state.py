"""SoAI - Reply queue task state resolution [backend/features/api/streaming/reply_queue_task_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tasks.enums import TaskStatus
from core.tasks.prompt_token_metadata import resolve_task_prompt_tokens
from core.tasks.streaming_prefill_timeout import resolve_streaming_first_chunk_timeout
from features.api.streaming.subscriptions import resolve_task_id_from_sources
from features.api.streaming.task_polling import task_to_complete_event

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.events.types_base import Event
    from core.logging.protocols import TraceLogger
    from core.runtime.protocols import RequestContextProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = (
    "reply_queue_inactivity_timeout_is_suspended",
    "resolve_reply_queue_terminal_event",
    "resolve_reply_queue_timeout_limit",
)

OPERATION_RESOLVE_TERMINAL_TASK_EVENT = (
    "api_streaming.iter_reply_queue_events.resolve_terminal_task_event"
)
OPERATION_RESOLVE_TIMEOUT_SUSPENSION = (
    "api_streaming.iter_reply_queue_events.resolve_timeout_suspension"
)


async def _load_task_noncritical(
    *,
    task_registry: TaskRegistryProtocol,
    task_id: str,
    logger: TraceLogger,
    trace_id: str,
    operation: str,
    message: str,
) -> Task | None:
    try:
        return await task_registry.get(task_id, force_refresh=True)
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            coerced,
            message=message,
            trace_id=trace_id,
            operation=operation,
            level="debug",
        )
    return None


async def resolve_reply_queue_terminal_event(
    *,
    task_registry: TaskRegistryProtocol,
    context: RequestContextProtocol | None,
    reply_queue: asyncio.Queue[Event],
    logger: TraceLogger,
    trace_id: str,
) -> Event | None:
    candidate_task_id = resolve_task_id_from_sources(
        context,
        reply_queue,
        task_registry=task_registry,
    )
    if candidate_task_id is None:
        return None
    task = await _load_task_noncritical(
        task_registry=task_registry,
        task_id=candidate_task_id,
        logger=logger,
        trace_id=trace_id,
        operation=OPERATION_RESOLVE_TERMINAL_TASK_EVENT,
        message="Failed to resolve terminal task event (non-critical).",
    )
    if task is None or not task.status.is_terminal():
        return None
    return task_to_complete_event(task)


async def reply_queue_inactivity_timeout_is_suspended(
    *,
    task_registry: TaskRegistryProtocol,
    task_id: str | None,
    logger: TraceLogger,
    trace_id: str,
) -> bool:
    if task_id is None:
        return False
    task = await _load_task_noncritical(
        task_registry=task_registry,
        task_id=task_id,
        logger=logger,
        trace_id=trace_id,
        operation=OPERATION_RESOLVE_TIMEOUT_SUSPENSION,
        message="Failed to resolve stream timeout suspension state (non-critical).",
    )
    if task is None:
        return False
    return task.status == TaskStatus.INPUT_REQUIRED


def _health_check_config(config: ConfigProtocol) -> JSONDict:
    return {
        "NON_STREAMING_TIMEOUT_SEC": config.get_float(
            "MODELS.ROUTING.HEALTH_CHECKS.NON_STREAMING_TIMEOUT_SEC",
        ),
        "STREAMING_PREFILL_MIN_TOKENS_PER_SEC": config.get_float(
            "MODELS.ROUTING.HEALTH_CHECKS.STREAMING_PREFILL_MIN_TOKENS_PER_SEC",
        ),
        "STREAMING_PREFILL_OVERHEAD_SEC": config.get_float(
            "MODELS.ROUTING.HEALTH_CHECKS.STREAMING_PREFILL_OVERHEAD_SEC",
        ),
    }


async def resolve_reply_queue_timeout_limit(
    *,
    task_registry: TaskRegistryProtocol,
    config: ConfigProtocol,
    task_id: str | None,
    inactivity_timeout: float,
    logger: TraceLogger,
    trace_id: str,
) -> float:
    if task_id is None:
        return inactivity_timeout
    task = await _load_task_noncritical(
        task_registry=task_registry,
        task_id=task_id,
        logger=logger,
        trace_id=trace_id,
        operation=OPERATION_RESOLVE_TIMEOUT_SUSPENSION,
        message="Failed to resolve stream timeout limit (non-critical).",
    )
    if task is None:
        return inactivity_timeout
    prompt_tokens = resolve_task_prompt_tokens(task)
    if prompt_tokens is None or prompt_tokens <= 0:
        return inactivity_timeout
    first_chunk_timeout = resolve_streaming_first_chunk_timeout(
        task=task,
        health_check_config=_health_check_config(config),
    )
    return max(inactivity_timeout, first_chunk_timeout)
