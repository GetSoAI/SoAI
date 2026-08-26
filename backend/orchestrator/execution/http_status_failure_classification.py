"""SoAI - HTTP status execution failure classification [backend/orchestrator/execution/http_status_failure_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import httpx2

from core.errors.error_types import ErrorType
from core.errors.http_error_responses import extract_http_response_message
from core.errors.http_status_classification import (
    resolve_execution_error_type_for_http_status,
)
from core.openai.chat_template_role_policy import is_chat_template_role_error_message
from orchestrator.execution.failure_classification_models import ExecutionFailureDetails

__all__ = (
    "build_chat_template_role_rejection_execution_failure",
    "classify_http_status_execution_failure",
)


def build_chat_template_role_rejection_execution_failure(
    task_id: str,
) -> ExecutionFailureDetails:
    return ExecutionFailureDetails(
        user_message=(
            "Backend rejected the chat message role sequence for its active chat template. "
            "SoAI tried every configured compatibility policy for this request."
        ),
        state_reason=f"Task {task_id} failed with chat-template role rejection.",
        log_stack=False,
        error_type=ErrorType.INVALID_REQUEST,
        affects_plugin_health=False,
        allow_failover=False,
    )


def classify_http_status_execution_failure(
    task_id: str,
    exception: httpx2.HTTPStatusError,
) -> ExecutionFailureDetails:
    response = exception.response
    status_code = response.status_code
    error_message = extract_http_response_message(response, status_code)
    if is_chat_template_role_error_message(error_message):
        return build_chat_template_role_rejection_execution_failure(task_id)
    error_type = resolve_execution_error_type_for_http_status(status_code)
    affects_plugin_health = status_code >= 500
    public_message = (
        f"Upstream backend rejected the request (HTTP {status_code})."
        if status_code < 500
        else "Upstream backend request failed."
    )
    return ExecutionFailureDetails(
        user_message=public_message,
        state_reason=f"Task {task_id} failed with HTTP {status_code}",
        log_stack=affects_plugin_health,
        error_type=error_type,
        affects_plugin_health=affects_plugin_health,
        allow_failover=True,
    )
