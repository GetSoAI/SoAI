"""SoAI - Upstream provider HTTP failure classification [backend/core/openai/provider_http_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.exceptions import ModelOutputContractError, SecurityError, SoAIError
from core.errors.external_service_exception import ExternalServiceError
from core.errors.http_status_classification import resolve_execution_error_type_for_http_status
from core.errors.status_mapping import error_type_to_status_code
from core.openai.context_overflow_validation import (
    build_context_overflow_validation_error,
)
from core.openai.model_output_contract_errors import (
    build_invalid_tool_call_json_error_details,
    is_invalid_tool_call_json_contract_error,
)
from core.openai.provider_error_explanations import (
    UpstreamFailureType,
    resolve_upstream_failure_error_type,
    resolve_upstream_failure_summary,
)
from core.openai.provider_error_reports import (
    OpenAIProviderErrorReport,
    extract_openai_provider_error_report,
    normalize_provider_request_reference,
)
from core.openai.provider_failure_classification import (
    classify_openai_provider_failure,
    resolve_provider_media_problem,
    resolve_rejected_provider_parameter,
)
from core.openai.provider_transport import build_openai_upstream_error_details
from core.timing.retry_backoff import normalize_retry_after_header

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_openai_provider_http_error",)

_REQUEST_REFERENCE_HEADERS: tuple[str, ...] = (
    "x-request-id",
    "request-id",
    "nvcf-reqid",
    "x-correlation-id",
)


def _resolve_request_reference(headers: Mapping[str, str] | None) -> str | None:
    if not headers:
        return None
    lowered = {str(name).lower(): value for name, value in headers.items()}
    for header_name in _REQUEST_REFERENCE_HEADERS:
        reference = normalize_provider_request_reference(lowered.get(header_name))
        if reference is not None:
            return reference
    return None


def _resolve_retry_after(headers: Mapping[str, str] | None) -> str | None:
    if not headers:
        return None
    lowered = {str(name).lower(): value for name, value in headers.items()}
    retry_after = normalize_retry_after_header(lowered.get("retry-after"))
    if retry_after is not None:
        return retry_after
    return normalize_retry_after_header(lowered.get("retry-after-ms"), milliseconds=True)


def _build_diagnostic_details(
    provider_name: str | None,
    *,
    status: int,
    report: OpenAIProviderErrorReport,
    headers: Mapping[str, str] | None,
) -> JSONDict:
    details = build_openai_upstream_error_details(
        provider_name,
        status=status,
        retry_after=_resolve_retry_after(headers),
    )
    for key, value in (
        ("upstream_explanation", report.explanation),
        ("upstream_error_type", report.error_type),
        ("upstream_error_code", report.code),
        ("upstream_error_param", resolve_rejected_provider_parameter(report)),
        ("upstream_request_reference", _resolve_request_reference(headers)),
    ):
        if value is not None:
            details[key] = value
    return details


def _request_model(request_payload: Mapping[str, JSONValue] | None) -> str | None:
    model_value = request_payload.get("model") if request_payload is not None else None
    return model_value.strip() or None if isinstance(model_value, str) else None


def build_openai_provider_http_error(
    provider_name: str | None,
    *,
    status: int,
    body_text: str | None,
    headers: Mapping[str, str] | None,
    request_payload: Mapping[str, JSONValue] | None,
    trace_id: str | None,
) -> SoAIError:
    report = extract_openai_provider_error_report(None, body_text=body_text)
    model = _request_model(request_payload)
    classification_status = status
    fallback_error_type = (
        ErrorType.SERVICE_UNAVAILABLE
        if status >= 500
        else (
            resolve_execution_error_type_for_http_status(status)
            if status
            else ErrorType.SERVER_ERROR
        )
    )
    if status == 0:
        try:
            fallback_error_type = ErrorType(report.error_type)
        except ValueError:
            fallback_error_type = ErrorType.SERVER_ERROR
        classification_status = (
            0
            if fallback_error_type is ErrorType.SERVER_ERROR
            else error_type_to_status_code(fallback_error_type)
        )
        if report.error_type in {"BadRequestError", "invalid_argument"}:
            classification_status = 400
    if status == 0 and report.code is not None and report.code.isdigit() and len(report.code) == 3:
        numeric_status = int(report.code)
        if 400 <= numeric_status <= 599:
            classification_status = numeric_status
    failure_type = classify_openai_provider_failure(classification_status, report, request_payload)
    details = _build_diagnostic_details(
        provider_name, status=status, report=report, headers=headers
    )
    details["upstream_failure_type"] = failure_type.value
    error_type = resolve_upstream_failure_error_type(failure_type, fallback_error_type)
    if status == 0:
        details["upstream_inferred_http_status"] = (
            classification_status or error_type_to_status_code(error_type)
        )
    if failure_type is UpstreamFailureType.INVALID_MEDIA:
        media_problem = resolve_provider_media_problem(
            report.provider_message or "", request_payload
        )
        if media_problem is not None:
            details["upstream_media_modality"], details["upstream_media_reason"] = media_problem
    context_overflow_error = build_context_overflow_validation_error(
        report.provider_message or "",
        model=model,
        code=report.code,
    )
    if context_overflow_error is not None and failure_type is UpstreamFailureType.CONTEXT_LENGTH:
        context_overflow_error.details = {**details, **(context_overflow_error.details or {})}
        return context_overflow_error
    tools_value = request_payload.get("tools") if request_payload is not None else None
    if failure_type in {
        UpstreamFailureType.INVALID_REQUEST,
        UpstreamFailureType.INVALID_PARAMETER,
    } and is_invalid_tool_call_json_contract_error(
        message=report.provider_message,
        error_type=report.error_type,
        tool_call_context=isinstance(tools_value, list),
    ):
        return ModelOutputContractError(
            "The selected model returned malformed tool-call JSON. Retry or select another model.",
            details=build_invalid_tool_call_json_error_details(
                provider=str(details["upstream_provider"]),
                source_model_id=model or "",
                provider_detail="The provider reported invalid tool-call JSON.",
                extra=details,
            ),
            trace_id=trace_id,
        )
    summary = resolve_upstream_failure_summary(failure_type, details)
    if failure_type in {UpstreamFailureType.AUTHENTICATION, UpstreamFailureType.PERMISSION}:
        error: SoAIError = SecurityError(summary, details=details, trace_id=trace_id)
    else:
        error = ExternalServiceError(summary, details=details, trace_id=trace_id)
    error.code = error_type.value
    error.http_status = error_type_to_status_code(error_type)
    return error
