"""SoAI - Execution-time request requirement failure classification [backend/orchestrator/execution/requirement_failure_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType
from core.errors.exceptions import ValidationError
from core.openai.context_overflow_validation import extract_context_overflow_validation
from core.openai.request_requirement_failures import (
    build_openai_request_requirement_failure_message,
    classify_openai_request_requirement_mismatch,
)
from orchestrator.execution.failure_classification_models import ExecutionFailureDetails

__all__ = ("classify_validation_execution_failure",)


def classify_validation_execution_failure(
    task_id: str,
    exception: ValidationError,
) -> ExecutionFailureDetails:
    context_overflow = extract_context_overflow_validation(str(exception), exception.details)
    if context_overflow is not None:
        return ExecutionFailureDetails(
            user_message=context_overflow.message,
            state_reason=f"Task {task_id} failed: context window exceeded.",
            log_stack=False,
            error_type=ErrorType.INVALID_REQUEST,
            affects_plugin_health=False,
            allow_failover=False,
        )
    mismatch = classify_openai_request_requirement_mismatch(
        message=str(exception),
        details=exception.details,
    )
    if mismatch is not None:
        normalized_message = build_openai_request_requirement_failure_message(mismatch)
        return ExecutionFailureDetails(
            user_message=normalized_message,
            state_reason=f"Task {task_id} failed: request requirements mismatch.",
            log_stack=False,
            error_type=ErrorType.INVALID_REQUEST,
            affects_plugin_health=False,
            allow_failover=False,
        )
    return ExecutionFailureDetails(
        user_message="Request validation failed.",
        state_reason=f"Task {task_id} failed: request validation error",
        log_stack=False,
        error_type=ErrorType.INVALID_REQUEST,
        affects_plugin_health=False,
        allow_failover=False,
    )
