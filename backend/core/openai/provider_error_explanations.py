"""SoAI - Upstream provider failure summaries and public explanations [backend/core/openai/provider_error_explanations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.payload import ErrorPublicPayload
from core.errors.status_mapping import error_type_to_status_code
from core.openai.context_overflow_validation import extract_context_overflow_validation
from core.openai.provider_error_reports import (
    normalize_provider_error_token,
    normalize_provider_request_reference,
)
from core.security.public_text_redaction import (
    PUBLIC_DIAGNOSTIC_TEXT_MAX_LENGTH,
    bound_public_text,
    sanitize_public_diagnostic_text,
)
from core.timing.retry_backoff import normalize_retry_after_header
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "PROVIDER_EXPLANATION_SEPARATOR",
    "UpstreamFailureType",
    "build_upstream_provider_public_error",
    "compose_provider_error_message",
    "build_provider_failure_explanation",
    "resolve_upstream_failure_summary",
    "resolve_upstream_failure_type",
    "resolve_upstream_failure_error_type",
    "split_provider_error_message",
)

PROVIDER_EXPLANATION_SEPARATOR = "\nProvider explanation: "


class UpstreamFailureType(str, Enum):
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    BILLING = "billing"
    RATE_LIMIT = "rate_limit"
    MODEL_UNAVAILABLE = "model_unavailable"
    CONTENT_POLICY = "content_policy"
    CONTEXT_LENGTH = "context_length"
    INVALID_PARAMETER = "invalid_parameter"
    INVALID_REQUEST = "invalid_request"
    INVALID_MEDIA = "invalid_media"
    UNSUPPORTED_VISION_REQUEST = "unsupported_vision_request"
    UNSUPPORTED_AUDIO_REQUEST = "unsupported_audio_request"
    TIMEOUT = "timeout"
    PROVIDER_OUTAGE = "provider_outage"


def _detail_text(details: Mapping[str, JSONValue], key: str, *, max_length: int) -> str | None:
    value = details.get(key)
    return sanitize_public_diagnostic_text(
        value if isinstance(value, str) else None, max_length=max_length
    )


def _rejected_parameter(details: Mapping[str, JSONValue]) -> str | None:
    return normalize_provider_error_token(details.get("upstream_error_param"))


def resolve_upstream_failure_summary(
    failure_type: UpstreamFailureType, details: Mapping[str, JSONValue]
) -> str:
    parameter = _rejected_parameter(details)
    if (
        failure_type in (UpstreamFailureType.INVALID_PARAMETER, UpstreamFailureType.INVALID_REQUEST)
        and parameter is not None
        and parameter.rsplit(".", 1)[-1] == "reasoning_content"
    ):
        return "The provider rejected preserved reasoning in the tool-call history. Select a provider that supports reasoning replay for this model."
    match failure_type:
        case UpstreamFailureType.AUTHENTICATION:
            return "The provider rejected the API key. Check the key configured for this provider."
        case UpstreamFailureType.PERMISSION:
            return "The provider denied access to this model or endpoint. Check the API key permissions, account entitlements and supported regions."
        case UpstreamFailureType.BILLING:
            return "The provider rejected the request because the account billing, credits or spend limit need attention."
        case UpstreamFailureType.RATE_LIMIT:
            return "The provider rate limit was reached. Wait before retrying or lower the request rate."
        case UpstreamFailureType.MODEL_UNAVAILABLE:
            return "The provider reported that the selected model is unavailable or does not exist. Select another model or refresh the provider catalog."
        case UpstreamFailureType.CONTENT_POLICY:
            return "The provider content policy blocked the request. Rephrase the message or select another model."
        case UpstreamFailureType.CONTEXT_LENGTH:
            return "The request exceeds the model context window. Compact the conversation, lower the max tokens setting or select a model with a larger context."
        case UpstreamFailureType.INVALID_PARAMETER:
            parameter = _rejected_parameter(details)
            if parameter is None:
                return "The provider rejected a model parameter. Review the model parameters and retry."
            return f"The provider rejected the '{parameter}' parameter. Change or reset '{parameter}' in the model parameters and retry."
        case UpstreamFailureType.INVALID_REQUEST:
            return "The provider rejected the request as invalid. Check the selected model and the request content."
        case UpstreamFailureType.INVALID_MEDIA:
            return "The provider rejected an attachment. Check its format, size and contents, or upload it again."
        case UpstreamFailureType.UNSUPPORTED_VISION_REQUEST:
            return "The provider rejected image input. Select a vision-capable model or remove the image."
        case UpstreamFailureType.UNSUPPORTED_AUDIO_REQUEST:
            return "The provider rejected audio input. Select an audio-capable model or remove the audio."
        case UpstreamFailureType.TIMEOUT:
            return "The provider timed out while processing the request. Retry, or shorten the request."
        case UpstreamFailureType.PROVIDER_OUTAGE:
            return "The provider is temporarily unavailable or overloaded. Retry later or select another provider."


def build_provider_failure_explanation(details: Mapping[str, JSONValue]) -> str | None:
    provider = _detail_text(details, "upstream_provider", max_length=80) or "The provider"
    status = details.get("upstream_http_status")
    facts = ""
    if is_strict_int(status) and status > 0:
        facts = f"{provider} returned HTTP {status}"
    elif details.get("upstream_transport_error") is True:
        facts = f"{provider} could not be reached"
    parameter = _rejected_parameter(details)
    if facts and parameter is not None:
        facts = f"{facts} for parameter '{parameter}'"
    retry_after = _detail_text(details, "upstream_retry_after", max_length=64)
    if facts and retry_after is not None:
        retry_unit = " seconds" if retry_after.isdigit() else ""
        facts = f"{facts}; retry after {retry_after}{retry_unit}"
    explanation = _detail_text(
        details, "upstream_explanation", max_length=PUBLIC_DIAGNOSTIC_TEXT_MAX_LENGTH
    )
    text = ": ".join(part for part in (facts, explanation) if part)
    return bound_public_text(text, max_length=PUBLIC_DIAGNOSTIC_TEXT_MAX_LENGTH) if text else None


def compose_provider_error_message(summary: str, explanation: str | None) -> str:
    normalized_summary = summary.strip()
    if not explanation:
        return normalized_summary
    return f"{normalized_summary}{PROVIDER_EXPLANATION_SEPARATOR}{explanation}"


def split_provider_error_message(message: str) -> tuple[str, str | None]:
    summary, separator, explanation = message.partition(PROVIDER_EXPLANATION_SEPARATOR)
    if not separator:
        return (message, None)
    return (summary.strip(), sanitize_public_diagnostic_text(explanation))


def resolve_upstream_failure_type(
    details: Mapping[str, JSONValue],
) -> UpstreamFailureType | None:
    value = details.get("upstream_failure_type")
    try:
        return UpstreamFailureType(value) if isinstance(value, str) else None
    except ValueError:
        return None


def resolve_upstream_failure_error_type(
    failure_type: UpstreamFailureType | None,
    fallback: ErrorType,
) -> ErrorType:
    match failure_type:
        case None:
            return fallback
        case UpstreamFailureType.AUTHENTICATION:
            return ErrorType.AUTHENTICATION_ERROR
        case UpstreamFailureType.PERMISSION:
            return ErrorType.FORBIDDEN
        case UpstreamFailureType.BILLING:
            return ErrorType.PAYMENT_REQUIRED
        case UpstreamFailureType.RATE_LIMIT:
            return ErrorType.RATE_LIMIT
        case UpstreamFailureType.TIMEOUT:
            return ErrorType.TIMEOUT_ERROR
        case UpstreamFailureType.PROVIDER_OUTAGE:
            return (
                fallback
                if fallback
                in {ErrorType.SERVER_ERROR, ErrorType.OVERLOADED, ErrorType.PLUGIN_UNAVAILABLE}
                else ErrorType.SERVICE_UNAVAILABLE
            )
        case UpstreamFailureType.MODEL_UNAVAILABLE:
            return (
                ErrorType.NOT_FOUND
                if fallback is ErrorType.NOT_FOUND
                else ErrorType.INVALID_REQUEST
            )
        case UpstreamFailureType.INVALID_REQUEST:
            return (
                fallback
                if fallback
                in {ErrorType.CONFLICT, ErrorType.MODEL_STOPPED, ErrorType.MODEL_DELETED}
                else ErrorType.INVALID_REQUEST
            )
        case _:
            return ErrorType.INVALID_REQUEST


def _build_public_details(
    details: Mapping[str, JSONValue],
    failure_type: UpstreamFailureType | None,
) -> JSONDict | None:
    public_details: JSONDict = {}
    if failure_type is not None:
        public_details["upstream_failure_type"] = failure_type.value
    if failure_type is UpstreamFailureType.CONTEXT_LENGTH:
        context_overflow = extract_context_overflow_validation("", details)
        if context_overflow is not None:
            public_details.update(
                {
                    key: value
                    for key, value in context_overflow.to_details().items()
                    if key != "model"
                }
            )
    for key in ("upstream_media_modality", "upstream_media_reason"):
        value = details.get(key)
        if isinstance(value, str) and value in {
            "vision",
            "audio",
            "format",
            "size",
            "decoding",
            "retrieval",
            "unspecified",
        }:
            public_details[key] = value
    status = details.get("upstream_http_status")
    if is_strict_int(status) and status > 0:
        public_details["upstream_http_status"] = status
    inferred_status = details.get("upstream_inferred_http_status")
    if is_strict_int(inferred_status) and 400 <= inferred_status <= 599:
        public_details["upstream_inferred_http_status"] = inferred_status
    retry_after_value = details.get("upstream_retry_after")
    retry_after = normalize_retry_after_header(
        retry_after_value if isinstance(retry_after_value, str) else None,
    )
    if retry_after is not None:
        public_details["retry_after"] = retry_after
    provider_code = normalize_provider_error_token(details.get("upstream_error_code"))
    if provider_code is not None:
        public_details["provider_error_code"] = provider_code
    reference_value = details.get("upstream_request_reference")
    request_reference = normalize_provider_request_reference(
        reference_value if isinstance(reference_value, str) else None
    )
    if request_reference is not None:
        public_details["provider_request_id"] = request_reference
    return public_details or None


def build_upstream_provider_public_error(
    details: Mapping[str, JSONValue] | None,
    *,
    error_type: ErrorType,
    fallback_message: str,
    trace_id: str | None,
) -> ErrorPublicPayload:
    source = details or {}
    failure_type = resolve_upstream_failure_type(source)
    error_type = resolve_upstream_failure_error_type(failure_type, error_type)
    if failure_type is None:
        summary = fallback_message
        explanation = _detail_text(
            source, "upstream_explanation", max_length=PUBLIC_DIAGNOSTIC_TEXT_MAX_LENGTH
        )
    else:
        summary = resolve_upstream_failure_summary(failure_type, source)
        explanation = build_provider_failure_explanation(source)
    return ErrorPublicPayload(
        code=error_type.value,
        message=compose_provider_error_message(summary, explanation),
        param=_rejected_parameter(source),
        details=_build_public_details(source, failure_type),
        http_status=error_type_to_status_code(error_type),
        trace_id=trace_id,
    )
