"""SoAI - Execution failure classification for task outcomes [backend/orchestrator/execution/failure_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

import httpx2

from core.errors.error_types import ErrorType
from core.errors.exceptions import (
    ApiError,
    ConfigurationError,
    IpcRemoteRequestError,
    SoAIError,
    SoAITimeoutError,
    ValidationError,
)
from core.errors.external_service_exception import ExternalServiceError
from core.errors.http_status_classification import resolve_execution_error_type_for_http_status
from core.errors.memory_exhaustion import (
    ACCELERATOR_MEMORY_EXHAUSTED_MESSAGE,
    SYSTEM_MEMORY_EXHAUSTED_MESSAGE,
)
from core.events.publication_errors import PublicationDeadlineExceededError
from core.ipc.remote_error_metadata import REMOTE_ERROR_CODE_KEY
from core.openai.context_overflow_validation import extract_context_overflow_validation
from orchestrator.execution.chat_template_role_policy import is_chat_template_role_policy_rejection
from orchestrator.execution.failure_classification_models import ExecutionFailureDetails
from orchestrator.execution.http_status_failure_classification import (
    build_chat_template_role_rejection_execution_failure,
    classify_http_status_execution_failure,
)
from orchestrator.execution.requirement_failure_classification import (
    classify_validation_execution_failure,
)
from orchestrator.execution.result_processing_error import ResultProcessingError
from orchestrator.execution.streaming import (
    ChunkDeliveryTimeoutError,
    InvalidStreamingChunk,
    StreamingIdleTimeoutError,
    StreamingSourceTimeoutError,
)
from orchestrator.execution.upstream_error_metadata import has_upstream_provider_marker
from orchestrator.execution.upstream_failure_classification import (
    build_upstream_provider_failure_details,
    should_allow_failover_for_external_upstream_error,
)

__all__ = (
    "ExecutionFailureDetails",
    "classify_execution_failure",
    "resolve_remote_error_code",
)


def _classify_api_execution_failure(
    task_id: str,
    exception: ApiError,
) -> ExecutionFailureDetails:
    error_type = resolve_execution_error_type_for_http_status(exception.http_status)
    affects_plugin_health = exception.http_status >= 500
    if exception.code == ErrorType.PLUGIN_UNAVAILABLE.value:
        user_message = "Plugin backend became unavailable. Retry after recovery completes."
    else:
        user_message = (
            exception.message if exception.http_status < 500 else "Request execution failed."
        )
    return ExecutionFailureDetails(
        user_message=user_message,
        state_reason=f"Task {task_id} failed with HTTP {exception.http_status}",
        log_stack=affects_plugin_health,
        error_type=error_type,
        affects_plugin_health=affects_plugin_health,
        allow_failover=should_allow_failover_for_external_upstream_error(error_type),
    )


def resolve_remote_error_code(exception: IpcRemoteRequestError) -> str | None:
    details = exception.details
    if not isinstance(details, dict):
        return None
    code_value = details.get(REMOTE_ERROR_CODE_KEY)
    if not isinstance(code_value, str):
        return None
    normalized_code = code_value.strip()
    return normalized_code or None


def _is_remote_model_output_contract_error(exception: IpcRemoteRequestError) -> bool:
    remote_error_code = resolve_remote_error_code(exception)
    return remote_error_code == ErrorType.MODEL_OUTPUT_CONTRACT.value


def _is_remote_invalid_request_error(exception: IpcRemoteRequestError) -> bool:
    remote_error_code = resolve_remote_error_code(exception)
    return remote_error_code == ErrorType.INVALID_REQUEST.value


def _classify_remote_memory_exhaustion(
    task_id: str,
    exception: IpcRemoteRequestError,
) -> ExecutionFailureDetails | None:
    remote_error_code = resolve_remote_error_code(exception)
    if remote_error_code == ErrorType.ACCELERATOR_MEMORY_EXHAUSTED.value:
        error_type = ErrorType.ACCELERATOR_MEMORY_EXHAUSTED
        user_message = ACCELERATOR_MEMORY_EXHAUSTED_MESSAGE
        state_reason = f"Task {task_id} failed: accelerator memory exhausted"
    elif remote_error_code == ErrorType.SYSTEM_MEMORY_EXHAUSTED.value:
        error_type = ErrorType.SYSTEM_MEMORY_EXHAUSTED
        user_message = SYSTEM_MEMORY_EXHAUSTED_MESSAGE
        state_reason = f"Task {task_id} failed: system memory exhausted"
    else:
        return None
    return ExecutionFailureDetails(
        user_message=user_message,
        state_reason=state_reason,
        log_stack=False,
        error_type=error_type,
        affects_plugin_health=False,
        allow_failover=True,
    )


def classify_execution_failure(
    task_id: str,
    exception: Exception,
    request_timeout: float,
) -> ExecutionFailureDetails:
    root_exception: Exception = exception
    if isinstance(exception, SoAIError) and (exception.__class__ is SoAIError):
        cause_exception = exception.cause
        if isinstance(cause_exception, Exception):
            root_exception = cause_exception
    if isinstance(root_exception, ChunkDeliveryTimeoutError):
        return ExecutionFailureDetails(
            user_message="Response delivery timed out.",
            state_reason=f"Task {task_id} failed: chunk delivery backpressure",
            log_stack=False,
            error_type=ErrorType.TIMEOUT_ERROR,
            affects_plugin_health=False,
            allow_failover=False,
        )
    if isinstance(root_exception, StreamingIdleTimeoutError):
        return ExecutionFailureDetails(
            user_message="The provider stream became idle.",
            state_reason=f"Task {task_id} failed: streaming idle timeout",
            log_stack=False,
            error_type=ErrorType.TIMEOUT_ERROR,
            affects_plugin_health=True,
            allow_failover=True,
        )
    if isinstance(root_exception, StreamingSourceTimeoutError):
        return ExecutionFailureDetails(
            user_message="The provider stream timed out.",
            state_reason=f"Task {task_id} failed: streaming source timeout",
            log_stack=False,
            error_type=ErrorType.TIMEOUT_ERROR,
            affects_plugin_health=True,
            allow_failover=True,
        )
    if isinstance(root_exception, asyncio.TimeoutError):
        return ExecutionFailureDetails(
            user_message=f"Request timed out after {request_timeout}s.",
            state_reason=f"Task {task_id} failed: request timeout",
            log_stack=False,
            error_type=ErrorType.TIMEOUT_ERROR,
            affects_plugin_health=True,
            allow_failover=True,
        )
    if isinstance(root_exception, httpx2.TimeoutException):
        return ExecutionFailureDetails(
            user_message=f"Request timed out after {request_timeout}s.",
            state_reason=f"Task {task_id} failed: upstream timeout",
            log_stack=False,
            error_type=ErrorType.TIMEOUT_ERROR,
            affects_plugin_health=True,
            allow_failover=True,
        )
    if isinstance(root_exception, httpx2.ConnectError):
        return ExecutionFailureDetails(
            user_message="Plugin backend service is unreachable.",
            state_reason=f"Task {task_id} failed: backend unreachable",
            log_stack=False,
            error_type=ErrorType.PLUGIN_UNAVAILABLE,
            affects_plugin_health=True,
            allow_failover=True,
        )
    if isinstance(root_exception, httpx2.RemoteProtocolError):
        return ExecutionFailureDetails(
            user_message="Plugin backend disconnected unexpectedly.",
            state_reason=f"Task {task_id} failed: backend protocol error",
            log_stack=False,
            error_type=ErrorType.PLUGIN_UNAVAILABLE,
            affects_plugin_health=True,
            allow_failover=True,
        )
    if isinstance(root_exception, httpx2.RequestError):
        return ExecutionFailureDetails(
            user_message="Plugin backend transport failed.",
            state_reason=f"Task {task_id} failed: backend transport error",
            log_stack=False,
            error_type=ErrorType.PLUGIN_UNAVAILABLE,
            affects_plugin_health=True,
            allow_failover=True,
        )
    if isinstance(root_exception, InvalidStreamingChunk):
        return ExecutionFailureDetails(
            user_message="Plugin returned an invalid streaming payload.",
            state_reason=f"Task {task_id} failed: invalid streaming payload",
            log_stack=True,
            error_type=ErrorType.INFERENCE_ERROR,
            affects_plugin_health=True,
            allow_failover=True,
        )
    if isinstance(root_exception, httpx2.HTTPStatusError) and root_exception.response is not None:
        return classify_http_status_execution_failure(task_id, root_exception)
    if isinstance(root_exception, ApiError):
        return _classify_api_execution_failure(task_id, root_exception)
    if isinstance(root_exception, SoAITimeoutError):
        publication_timeout = isinstance(root_exception, PublicationDeadlineExceededError)
        failure_label = "orchestration publication timeout" if publication_timeout else "timeout"
        return ExecutionFailureDetails(
            user_message="Request timed out.",
            state_reason=f"Task {task_id} failed: {failure_label}",
            log_stack=False,
            error_type=ErrorType.TIMEOUT_ERROR,
            affects_plugin_health=not publication_timeout,
            allow_failover=not publication_timeout,
        )
    if isinstance(root_exception, IpcRemoteRequestError):
        memory_failure = _classify_remote_memory_exhaustion(task_id, root_exception)
        if memory_failure is not None:
            return memory_failure
    if isinstance(root_exception, IpcRemoteRequestError) and _is_remote_model_output_contract_error(
        root_exception,
    ):
        return ExecutionFailureDetails(
            user_message="Model output violated the required response contract.",
            state_reason=f"Task {task_id} failed: model output contract violation",
            log_stack=False,
            error_type=ErrorType.MODEL_OUTPUT_CONTRACT,
            affects_plugin_health=False,
            allow_failover=False,
        )
    if isinstance(root_exception, IpcRemoteRequestError) and _is_remote_invalid_request_error(
        root_exception,
    ):
        context_overflow = extract_context_overflow_validation(
            str(root_exception),
            root_exception.details,
        )
        if context_overflow is not None:
            return ExecutionFailureDetails(
                user_message=context_overflow.message,
                state_reason=f"Task {task_id} failed: remote context window exceeded.",
                log_stack=False,
                error_type=ErrorType.INVALID_REQUEST,
                affects_plugin_health=False,
                allow_failover=False,
            )
        return ExecutionFailureDetails(
            user_message="Request validation failed.",
            state_reason=f"Task {task_id} failed: remote request validation error.",
            log_stack=False,
            error_type=ErrorType.INVALID_REQUEST,
            affects_plugin_health=False,
            allow_failover=False,
        )
    if isinstance(root_exception, IpcRemoteRequestError) and is_chat_template_role_policy_rejection(
        root_exception,
    ):
        return build_chat_template_role_rejection_execution_failure(task_id)
    if isinstance(root_exception, IpcRemoteRequestError) and has_upstream_provider_marker(
        root_exception,
    ):
        return build_upstream_provider_failure_details(task_id, root_exception)
    if isinstance(root_exception, IpcRemoteRequestError):
        return ExecutionFailureDetails(
            user_message="Plugin backend became unavailable.",
            state_reason=f"Task {task_id} failed: plugin worker request failed",
            log_stack=True,
            error_type=ErrorType.PLUGIN_UNAVAILABLE,
            affects_plugin_health=True,
            allow_failover=True,
        )
    if isinstance(root_exception, ValidationError):
        return classify_validation_execution_failure(task_id, root_exception)
    if isinstance(root_exception, ConfigurationError):
        return ExecutionFailureDetails(
            user_message="Request configuration is invalid.",
            state_reason=f"Task {task_id} failed: configuration error",
            log_stack=False,
            error_type=ErrorType.INVALID_REQUEST,
            affects_plugin_health=False,
            allow_failover=False,
        )
    if isinstance(root_exception, ExternalServiceError) and is_chat_template_role_policy_rejection(
        root_exception,
    ):
        return build_chat_template_role_rejection_execution_failure(task_id)
    if isinstance(root_exception, ExternalServiceError):
        if has_upstream_provider_marker(root_exception):
            return build_upstream_provider_failure_details(task_id, root_exception)
        return ExecutionFailureDetails(
            user_message="Upstream service request failed.",
            state_reason=f"Task {task_id} failed: upstream service error",
            log_stack=True,
            error_type=ErrorType.SERVER_ERROR,
            affects_plugin_health=True,
            allow_failover=True,
        )
    if isinstance(root_exception, ResultProcessingError):
        return ExecutionFailureDetails(
            user_message="Internal result processing failed.",
            state_reason=f"Task {task_id} failed: internal result processing error",
            log_stack=True,
            error_type=ErrorType.SERVER_ERROR,
            affects_plugin_health=False,
            allow_failover=False,
        )
    return ExecutionFailureDetails(
        user_message="Request execution failed.",
        state_reason=f"Task {task_id} failed: unexpected execution error",
        log_stack=True,
        error_type=ErrorType.SERVER_ERROR,
        affects_plugin_health=True,
        allow_failover=True,
    )
