"""SoAI - MCP inference task failure finalization helpers [backend/mcp/registry/inference_task_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("finalize_inference_task_failed_noncritical",)

OPERATION_MCP_REGISTRY_INFERENCE_TASK_FAILURES_FINALIZE_INFERENCE_TASK_FAILED_NONCRITICAL = (
    "mcp.registry.inference_task_failures.finalize_inference_task_failed_noncritical"
)


async def finalize_inference_task_failed_noncritical(
    *,
    task_registry: TaskRegistryProtocol,
    task_id: str,
    error_code: int,
    error_message: str,
    logger: LoggerProtocol,
    trace_id: str | None,
    operation: str,
) -> None:
    try:
        await finalize(
            task_registry,
            task_id,
            TaskStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
        )
    except RECOVERABLE_EXCEPTIONS as fail_exception:
        log_handled_exception(
            logger,
            fail_exception,
            message="Failed to mark MCP inference task as failed (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_MCP_REGISTRY_INFERENCE_TASK_FAILURES_FINALIZE_INFERENCE_TASK_FAILED_NONCRITICAL,
            details={"task_id": task_id, "finalize_operation": operation},
            level="debug",
        )
