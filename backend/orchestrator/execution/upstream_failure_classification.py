"""SoAI - Upstream-provider failure classification helpers [backend/orchestrator/execution/upstream_failure_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType
from core.errors.exceptions import IpcRemoteRequestError
from core.errors.external_service_exception import ExternalServiceError
from core.errors.http_status_classification import (
    resolve_execution_error_type_for_http_status,
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
    exception: ExternalServiceError | IpcRemoteRequestError,
) -> ErrorType:
    if is_upstream_transport_error(exception):
        return ErrorType.PLUGIN_UNAVAILABLE
    status_code = resolve_upstream_http_status(exception)
    if status_code is None:
        return ErrorType.SERVER_ERROR
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
    exception: ExternalServiceError | IpcRemoteRequestError,
) -> ExecutionFailureDetails:
    resolved_error_type = resolve_external_upstream_error_type(exception)
    upstream_status_code = resolve_upstream_http_status(exception)
    should_log_stack = bool(upstream_status_code is not None and upstream_status_code >= 500)
    return ExecutionFailureDetails(
        user_message=exception.message,
        state_reason=f"Task {task_id} failed: upstream provider error",
        log_stack=should_log_stack,
        error_type=resolved_error_type,
        affects_plugin_health=False,
        allow_failover=should_allow_failover_for_external_upstream_error(resolved_error_type),
    )
