"""SoAI - Subagent active inference cancellation [backend/features/agent/subagents/coordinator/cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tasks.task_cancellation import request_cancellation_scope
from features.agent.subagents.reads import load_subagent_turn_record_noncritical

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("cancel_subagent_active_inference_scope_noncritical",)

OPERATION_SUBAGENT_CANCEL_ACTIVE_INFERENCE_SCOPE = (
    "agent.subagents.coordinator.cancellation.cancel_active_inference_scope"
)


async def cancel_subagent_active_inference_scope_noncritical(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    trace_id: str,
    conv_id: str,
    user_id: int,
    subagent_id: str,
    reason: str,
    operation: str,
    log_message: str,
) -> None:
    normalized_subagent_id = str(subagent_id or "").strip()
    if not normalized_subagent_id or user_id <= 0:
        return
    turn_record = await load_subagent_turn_record_noncritical(
        database_agent_turns=api_dependencies.database_agent_turns,
        logger=logger,
        trace_id=trace_id,
        conv_id=conv_id,
        user_id=user_id,
        subagent_id=normalized_subagent_id,
    )
    active_inference_cancellation_id = (
        str(turn_record.get("active_inference_cancellation_id") or "").strip()
        if isinstance(turn_record, dict)
        else ""
    )
    if not active_inference_cancellation_id:
        return
    try:
        await request_cancellation_scope(
            api_dependencies.task_registry,
            active_inference_cancellation_id,
            reason,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            logger,
            coerced,
            message=log_message,
            trace_id=trace_id,
            operation=OPERATION_SUBAGENT_CANCEL_ACTIVE_INFERENCE_SCOPE,
            level="warning",
            details={
                "conv_id": conv_id,
                "turn_id": normalized_subagent_id,
                "cancellation_id": active_inference_cancellation_id,
            },
        )
