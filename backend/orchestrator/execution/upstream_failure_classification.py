"""SoAI - Upstream-provider failure classification helpers [backend/orchestrator/execution/upstream_failure_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType
from core.errors.exceptions import SoAIError
from core.errors.http_status_classification import (
    resolve_execution_error_type_for_http_status,
)
from core.openai.openai_sse_error_escalation import OpenAIStreamError
from core.openai.provider_error_explanations import (
    UpstreamFailureType,
    build_upstream_provider_public_error,
    resolve_upstream_failure_error_type,
    resolve_upstream_failure_type,
)
from orchestrator.execution.failure_classification_models import ExecutionFailureDetails
from orchestrator.execution.upstream_error_metadata import (
    is_upstream_transport_error,
    resolve_upstream_http_status,
)

__all__ = (
    "build_upstream_provider_failure_details",
    "resolve_external_upstream_error_type",
    "should_allow_failover_for_external_upstream_error",
)


def resolve_external_upstream_error_type(
    exception: SoAIError,
) -> ErrorType:
    if is_upstream_transport_error(exception):
        return ErrorType.PLUGIN_UNAVAILABLE
    status_code = resolve_upstream_http_status(exception)
    if status_code is None:
        try:
            return ErrorType(exception.code)
        except ValueError:
            return ErrorType.SERVER_ERROR
    if (
        resolve_upstream_failure_type(exception.details or {})
        is UpstreamFailureType.PROVIDER_OUTAGE
    ):
        return ErrorType.SERVICE_UNAVAILABLE
    return resolve_execution_error_type_for_http_status(status_code)


def should_allow_failover_for_external_upstream_error(
    resolved_error_type: ErrorType,
) -> bool:
    return resolved_error_type in {
        ErrorType.OVERLOADED,
        ErrorType.PLUGIN_UNAVAILABLE,
        ErrorType.TIMEOUT_ERROR,
        ErrorType.SERVER_ERROR,
    }


def build_upstream_provider_failure_details(
    task_id: str,
    exception: SoAIError,
) -> ExecutionFailureDetails:
    status_error_type = resolve_external_upstream_error_type(exception)
    resolved_error_type = resolve_upstream_failure_error_type(
        resolve_upstream_failure_type(exception.details or {}), status_error_type
    )
    upstream_status_code = resolve_upstream_http_status(exception)
    should_log_stack = bool(upstream_status_code is not None and upstream_status_code >= 500)
    public_error = build_upstream_provider_public_error(
        exception.details,
        error_type=resolved_error_type,
        fallback_message="Upstream provider request failed. Review the provider configuration and retry.",
        trace_id=exception.trace_id,
    )
    return ExecutionFailureDetails(
        user_message=public_error.message,
        state_reason=f"Task {task_id} failed: upstream provider error",
        log_stack=should_log_stack,
        error_type=resolved_error_type,
        affects_plugin_health=(
            isinstance(exception, OpenAIStreamError)
            and exception.provider_id is None
            and exception.http_status >= 500
        ),
        allow_failover=(
            resolved_error_type is ErrorType.PAYMENT_REQUIRED
            or resolved_error_type is ErrorType.RATE_LIMIT
            or should_allow_failover_for_external_upstream_error(resolved_error_type)
            or resolved_error_type is ErrorType.SERVICE_UNAVAILABLE
        ),
        public_error=public_error,
    )
