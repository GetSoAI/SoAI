"""SoAI - Core exception type definitions and payloads [backend/core/errors/exceptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Never, SupportsIndex, override

from core.errors.error_initialization import build_error_init_kwargs
from core.errors.error_types import ErrorType
from core.errors.messages import resolve_error_message
from core.errors.operation_resolution import resolve_default_operation

if TYPE_CHECKING:
    import asyncio
    import subprocess

    from core.types.json import JSONValue

__all__ = (
    "CONVERSATION_INPUT_NOT_CANCELLABLE_CODE",
    "ApiError",
    "AcceleratorMemoryExhaustedError",
    "ArchivedConversationLimitError",
    "AutomationRevisionConflictError",
    "BackendUpdateContainmentError",
    "ConcurrencyError",
    "ConfigurationError",
    "ConflictError",
    "ConversationInputNotCancellableError",
    "DatabaseError",
    "DurableDeliveryDeferredError",
    "EditionUnavailableError",
    "FeatureDisabledError",
    "GPUControlInputValidationError",
    "InsufficientDiskSpaceError",
    "IpcRemoteRequestError",
    "ModelOutputContractError",
    "NotFoundError",
    "OneShotAutomationStartNotFutureError",
    "PayloadTooLargeError",
    "PreconditionError",
    "ProcessError",
    "ProcessGroupCleanupError",
    "RateLimitError",
    "SecurityError",
    "ServiceUnavailableError",
    "SoAIError",
    "SoAITimeoutError",
    "StateError",
    "SystemMemoryExhaustedError",
    "TaskConcurrencyLimitError",
    "ValidationError",
)

CONVERSATION_INPUT_NOT_CANCELLABLE_CODE = "conversation_input_not_cancellable"


class SoAIError(Exception):
    code: str | int = "internal_error"
    http_status: int = 500
    is_transient: bool = False
    public_message: str | None = None
    public_param: str | None = None
    public_details: Mapping[str, JSONValue] | None = None

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, JSONValue] | None = None,
        operation: str | None = None,
        cause: BaseException | None = None,
        trace_id: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        resolved_message = resolve_error_message(message, default_message=type(self).__name__)
        super().__init__(resolved_message)
        self.message = resolved_message
        self.details = dict(details) if details else None
        self.operation = operation or resolve_default_operation()
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause
        self.trace_id = trace_id
        self.headers = dict(headers) if headers else None

    @override
    def __str__(self) -> str:
        return self.message

    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return (
            (self.message,),
            {
                "details": self.details,
                "operation": self.operation,
                "cause": self.cause,
                "trace_id": self.trace_id,
                "headers": self.headers,
            },
        )


class ApiError(SoAIError):
    def __init__(
        self,
        message: str,
        *,
        code: str | int,
        http_status: int,
        details: Mapping[str, JSONValue] | None = None,
        operation: str | None = None,
        cause: BaseException | None = None,
        trace_id: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        error_kwargs = build_error_init_kwargs(details, operation, cause, trace_id, headers)
        super().__init__(
            message,
            **error_kwargs,
        )
        self.code = code
        self.http_status = http_status

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        arguments, keywords = super().__getnewargs_ex__()
        return arguments, {**keywords, "code": self.code, "http_status": self.http_status}


class ValidationError(SoAIError):
    code: str | int = ErrorType.INVALID_REQUEST.value
    http_status = 422


class GPUControlInputValidationError(ValidationError): ...


class OneShotAutomationStartNotFutureError(ValidationError):
    code: str | int = "automation_one_shot_start_not_future"


class ModelOutputContractError(SoAIError):
    code: str | int = ErrorType.MODEL_OUTPUT_CONTRACT.value
    http_status = 502


class PayloadTooLargeError(SoAIError):
    code: str | int = "payload_too_large"
    http_status = 413


class PreconditionError(SoAIError):
    code: str | int = "precondition_failed"
    http_status = 412


class AutomationRevisionConflictError(PreconditionError):
    code: str | int = "automation_revision_conflict"


class InsufficientDiskSpaceError(SoAIError):
    code: str | int = "insufficient_disk_space"
    http_status = 507
    public_message: str | None = "Not enough storage headroom. Free space or wait, then retry."


class AcceleratorMemoryExhaustedError(SoAIError):
    code: str | int = ErrorType.ACCELERATOR_MEMORY_EXHAUSTED.value
    http_status = 507


class SystemMemoryExhaustedError(SoAIError):
    code: str | int = ErrorType.SYSTEM_MEMORY_EXHAUSTED.value
    http_status = 507


class NotFoundError(SoAIError):
    code: str | int = ErrorType.NOT_FOUND.value
    http_status = 404


class ConfigurationError(SoAIError):
    code: str | int = "config_error"
    http_status = 500


class FeatureDisabledError(SoAIError):
    code: str | int = "feature_disabled"
    http_status = 503


class EditionUnavailableError(SoAIError):
    code: str | int = "edition_unavailable"
    http_status = 412


class IpcRemoteRequestError(SoAIError):
    code: str | int = "ipc_remote_request_error"
    http_status = 502


class ServiceUnavailableError(SoAIError):
    code: str | int = ErrorType.SERVICE_UNAVAILABLE.value
    http_status = 503
    is_transient = True


class DurableDeliveryDeferredError(ServiceUnavailableError):
    code: str | int = "durable_delivery_deferred"


class SecurityError(SoAIError):
    code: str | int = "security_error"
    http_status = 403


class StateError(SoAIError):
    code: str | int = "invalid_state"
    http_status = 409


class BackendUpdateContainmentError(StateError):
    code: str | int = "backend_update_containment_failed"


class ConcurrencyError(SoAIError):
    code: str | int = "concurrency_error"
    http_status = 409


class ConflictError(SoAIError):
    code: str | int = ErrorType.CONFLICT.value
    http_status = 409


class ArchivedConversationLimitError(ConflictError):
    code: str | int = "archive_limit_reached"


class ConversationInputNotCancellableError(ConflictError):
    code: str | int = CONVERSATION_INPUT_NOT_CANCELLABLE_CODE


class RateLimitError(SoAIError):
    code: str | int = ErrorType.RATE_LIMIT.value
    http_status = 429
    is_transient = True


class TaskConcurrencyLimitError(ConcurrencyError):
    def __init__(self, owner_type: str, owner_id: str, limit: int) -> None:
        self.owner_type = owner_type
        self.owner_id = owner_id
        self.limit = limit
        super().__init__(f"Maximum concurrent tasks ({limit}) exceeded for {owner_type}:{owner_id}")

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return ((self.owner_type, self.owner_id, self.limit), {})


class SoAITimeoutError(SoAIError):
    code: str | int = ErrorType.TIMEOUT_ERROR.value
    http_status = 504
    is_transient = True


class ProcessError(SoAIError):
    code: str | int = "process_error"
    http_status = 500


class ProcessGroupCleanupError(ProcessError):
    def __init__(
        self,
        message: str,
        *,
        process: subprocess.Popen[str] | subprocess.Popen[bytes],
        read_connections: tuple[tuple[asyncio.ReadTransport, asyncio.StreamReader], ...] = (),
        stdin_writer: asyncio.StreamWriter | None = None,
        operation: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(
            message,
            operation=operation,
            cause=cause,
            details={"process_group_exit": "unverified"},
        )
        self.process = process
        self.read_connections = read_connections
        self.stdin_writer = stdin_writer
        self.owned_cleanup_callbacks: list[Callable[[], Awaitable[None]]] = []

    @override
    def __str__(self) -> str:
        if self.process.returncode is None:
            return self.message
        return f"{self.message} Owned group exit was later verified."

    @override
    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        raise TypeError(
            "Owned process-group authority cannot be reconstructed outside its runtime."
        )


class DatabaseError(SoAIError):
    code: str | int = "database_error"
    http_status = 503
    is_transient = True
