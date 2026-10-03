"""SoAI - OpenAI SSE error escalation [backend/core/openai/openai_sse_error_escalation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal, NoReturn

from core.errors.error_types import ErrorType
from core.errors.exceptions import ApiError
from core.openai.chat_template_role_rejection import (
    CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY,
    CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY_KEY,
    is_chat_template_role_error_message,
)
from core.openai.context_overflow_validation import extract_context_overflow_validation
from core.openai.request_requirement_failures import (
    build_openai_request_requirement_failure_details,
    build_openai_request_requirement_failure_message,
    classify_openai_request_requirement_mismatch,
)
from core.openai.stream_error_diagnostics import StreamErrorDiagnostic

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("raise_openai_streaming_error",)


@dataclass(eq=False, repr=False, slots=True, kw_only=True)
class OpenAIStreamError(ApiError):
    message: str = field(kw_only=False)
    code: str | int
    http_status: int
    diagnostic: StreamErrorDiagnostic
    provider_id: str | None
    operation: str | None
    origin: Literal["upstream", "local_terminal"]
    details: dict[str, JSONValue] | None = None

    def __post_init__(self) -> None:
        ApiError.__init__(
            self,
            self.message,
            code=self.code,
            http_status=self.http_status,
            details=self.details,
            operation=self.operation,
        )


def _resolve_openai_sse_error_http_status(error_type: str) -> int:
    match error_type:
        case ErrorType.AUTHENTICATION_ERROR.value:
            return 401
        case ErrorType.FORBIDDEN.value:
            return 403
        case ErrorType.NOT_FOUND.value:
            return 404
        case (
            ErrorType.CONFLICT.value | ErrorType.MODEL_STOPPED.value | ErrorType.MODEL_DELETED.value
        ):
            return 409
        case ErrorType.RATE_LIMIT.value:
            return 429
        case ErrorType.INVALID_REQUEST.value:
            return 422
        case ErrorType.TIMEOUT_ERROR.value:
            return 504
        case (
            ErrorType.SERVICE_UNAVAILABLE.value
            | ErrorType.PLUGIN_UNAVAILABLE.value
            | ErrorType.OVERLOADED.value
        ):
            return 503
        case ErrorType.SERVER_ERROR.value:
            return 500
        case _:
            return 500


def raise_openai_streaming_error(
    parsed_error: tuple[str, str | None, str | None, str | None],
    *,
    operation: str,
    provider_id: str | None = None,
    task_id: str | None = None,
    trace_id: str | None = None,
    origin: Literal["upstream", "local_terminal"] = "upstream",
) -> NoReturn:
    upstream_message, error_type, upstream_param, upstream_code = parsed_error
    if origin == "local_terminal":
        local_error_type = error_type.strip() if isinstance(error_type, str) else ""
        local_error_type = local_error_type or ErrorType.SERVER_ERROR.value
        raise OpenAIStreamError(
            upstream_message,
            code=local_error_type,
            http_status=_resolve_openai_sse_error_http_status(local_error_type),
            operation=operation,
            diagnostic=StreamErrorDiagnostic.from_error(
                category="local_terminal_error",
                source="local_terminal",
                upstream_type=None,
                upstream_code=None,
                upstream_param=None,
                provider_id=None,
                operation=operation,
                task_id=task_id,
                trace_id=trace_id,
                mapped_status=_resolve_openai_sse_error_http_status(local_error_type),
                provider_prose_omitted=False,
            ),
            provider_id=None,
            origin=origin,
        )
    context_overflow = extract_context_overflow_validation(
        upstream_message,
        None,
        code=upstream_code,
    )
    if context_overflow is not None:
        context_overflow = replace(context_overflow, model=None)
        raise OpenAIStreamError(
            context_overflow.message,
            code=ErrorType.INVALID_REQUEST.value,
            http_status=422,
            details=context_overflow.to_details(),
            operation=operation,
            diagnostic=StreamErrorDiagnostic.from_error(
                category="invalid_request_error",
                source="context_overflow",
                upstream_type=error_type,
                upstream_code=upstream_code,
                upstream_param=upstream_param,
                provider_id=provider_id,
                operation=operation,
                task_id=task_id,
                trace_id=trace_id,
                mapped_status=422,
                requested_tokens=context_overflow.requested_tokens,
                available_tokens=context_overflow.available_tokens,
            ),
            provider_id=provider_id,
            origin=origin,
        )
    mismatch = classify_openai_request_requirement_mismatch(message=upstream_message)
    if mismatch is not None:
        raise OpenAIStreamError(
            build_openai_request_requirement_failure_message(mismatch),
            code=ErrorType.INVALID_REQUEST.value,
            http_status=422,
            details=build_openai_request_requirement_failure_details(mismatch),
            operation=operation,
            diagnostic=StreamErrorDiagnostic.from_error(
                category="invalid_request_error",
                source="request_requirement",
                upstream_type=error_type,
                upstream_code=upstream_code,
                upstream_param=upstream_param,
                provider_id=provider_id,
                operation=operation,
                task_id=task_id,
                trace_id=trace_id,
                mapped_status=422,
                missing_capabilities=mismatch.missing_capabilities,
                missing_modalities=mismatch.missing_modalities,
            ),
            provider_id=provider_id,
            origin=origin,
        )
    normalized_error_type = (error_type or ErrorType.SERVER_ERROR.value).strip()
    normalized_error_type = normalized_error_type or ErrorType.SERVER_ERROR.value
    if normalized_error_type == "BadRequestError":
        normalized_error_type = ErrorType.INVALID_REQUEST.value
    if normalized_error_type not in {member.value for member in ErrorType}:
        normalized_error_type = ErrorType.SERVER_ERROR.value
    status = _resolve_openai_sse_error_http_status(normalized_error_type)
    diagnostic = StreamErrorDiagnostic.from_error(
        category=normalized_error_type,
        source="sse_error_frame",
        upstream_type=error_type,
        upstream_code=upstream_code,
        upstream_param=upstream_param,
        provider_id=provider_id,
        operation=operation,
        task_id=task_id,
        trace_id=trace_id,
        mapped_status=status,
    )
    if normalized_error_type == ErrorType.PLUGIN_UNAVAILABLE.value:
        raise OpenAIStreamError(
            "Plugin backend became unavailable. Retry after recovery completes.",
            code=normalized_error_type,
            http_status=503,
            operation=operation,
            diagnostic=diagnostic,
            provider_id=provider_id,
            origin=origin,
        )
    if status in (422, 500) and is_chat_template_role_error_message(upstream_message):
        raise OpenAIStreamError(
            "Backend rejected the chat message role sequence for its active chat template.",
            code=ErrorType.INVALID_REQUEST.value,
            http_status=422,
            details={
                CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY_KEY: CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY
            },
            operation=operation,
            diagnostic=replace(
                diagnostic,
                category=CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY,
                source=CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY,
                mapped_status=422,
            ),
            provider_id=provider_id,
            origin=origin,
        )
    raise OpenAIStreamError(
        (
            "Upstream provider rejected the request."
            if status < 500
            else "Upstream provider request failed."
        ),
        code=normalized_error_type,
        http_status=status,
        operation=operation,
        diagnostic=diagnostic,
        provider_id=provider_id,
        origin=origin,
    )
