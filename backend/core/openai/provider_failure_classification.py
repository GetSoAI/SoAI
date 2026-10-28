"""SoAI - Provider-agnostic upstream failure classification [backend/core/openai/provider_failure_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.openai.capability_taxonomy import OpenAIModality
from core.openai.modalities import collect_message_modalities
from core.openai.provider_error_explanations import UpstreamFailureType
from core.openai.provider_error_reports import normalize_provider_error_token

if TYPE_CHECKING:
    from core.openai.provider_error_reports import OpenAIProviderErrorReport
    from core.types.json import JSONValue

__all__ = (
    "classify_openai_provider_failure",
    "resolve_rejected_provider_parameter",
    "resolve_provider_media_problem",
)

_MODEL_PARAM = "model"
_TIMEOUT_STATUSES = frozenset((408, 504, 524))
_BILLING_SIGNALS = frozenset(
    (
        "insufficient_quota",
        "billing_hard_limit_reached",
        "billing_not_active",
        "payment_required",
        "credit_balance_exhausted",
        "insufficient_credits",
        "insufficient_balance",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
    )
)
_AUTHENTICATION_SIGNALS = frozenset(
    ("invalid_api_key", "api_key_invalid", "authentication_error", "unauthenticated")
)
_PERMISSION_SIGNALS = frozenset(
    (
        "permission_denied",
        "permission_error",
        "forbidden_error",
        "unsupported_country_region_territory",
    )
)
_CONTENT_POLICY_SIGNALS = frozenset(
    ("content_filter", "content_policy_violation", "responsibleaipolicyviolation")
)
_CONTEXT_LENGTH_SIGNALS = frozenset(("context_length_exceeded", "context_window_exceeded"))
_INVALID_PARAMETER_SIGNALS = frozenset(
    ("invalid_parameter", "unsupported_parameter", "parameter_out_of_range")
)
_INVALID_REQUEST_SIGNALS = frozenset(("invalid_request_error", "bad_request", "400"))
_RATE_LIMIT_SIGNALS = frozenset(
    ("rate_limit_exceeded", "rate_limit_error", "slow_down", "resource_exhausted", "throttled")
)
_MODEL_UNAVAILABLE_SIGNALS = frozenset(
    (
        "model_not_found",
        "model_not_available",
        "model_unavailable",
        "deploymentnotfound",
        "not_found_error",
    )
)
_OUTAGE_SIGNALS = frozenset(("server_is_overloaded", "overloaded_error", "unavailable"))
_TIMEOUT_SIGNALS = frozenset(("deadline_exceeded", "request_timeout"))
_BILLING_MESSAGE_SOURCE = (
    r"(?i)\binsufficient[\s_]+(?:credits?|balance|funds|quota)\b|\bcredits?\s+(?:have\s+)?"
    r"(?:expired|exhausted|depleted)\b|\bout\s+of\s+credits\b|\bcredit\s+balance\b|\bbilling\b"
    r"|\bpayment\s+required\b|\bspend(?:ing)?\s+limit\b|\bexceeded\s+your\s+current\s+quota\b"
)
_AUTHENTICATION_MESSAGE_SOURCE = (
    r"(?i)\b(?:invalid|incorrect|missing|expired|revoked|no)\s+(?:api[\s_-]*key|authentication"
    r"|auth(?:orization)?\s+(?:token|header)|bearer\s+token|access\s+token)\b|\bapi[\s_-]*key\s+"
    r"(?:is\s+)?(?:not\s+valid|invalid|expired|missing|required)\b|\bunauthenticated\b"
)
_PERMISSION_MESSAGE_SOURCE = (
    r"(?i)\b(?:country|region|territory|location)\b[^.]{0,40}\bnot\s+supported\b"
    r"|\bpermission\s+denied\b|\baccess\s+(?:is\s+)?denied\b"
    r"|\bnot\s+(?:authorized|entitled|allowed)\s+to\s+(?:access|use)\b"
)
_CONTENT_POLICY_MESSAGE_SOURCE = (
    r"(?i)\bcontent[\s_]+(?:management\s+)?(?:policy|filter(?:ing)?)\b|\bsafety\s+system\b"
    r"|\busage\s+polic(?:y|ies)\b|\bresponsible\s*ai\b|\bflagged\s+(?:as|by|for)\b"
)
_RATE_LIMIT_MESSAGE_SOURCE = (
    r"(?i)\brate[\s_-]*limit|\btoo\s+many\s+requests\b|\bthrottl|\bresource\s+(?:has\s+been\s+)?"
    r"exhausted\b|\bResourceExhausted\b|\bquota\s+exceeded\b"
)
_CONTEXT_LENGTH_MESSAGE_SOURCE = (
    r"(?i)\bcontext\s+(?:length|window|limit|size)\b|\b(?:prompt|input)\s+is\s+too\s+long\b"
    r"|\btoo\s+many\s+(?:input\s+)?tokens\b|\bexceeds?\s+the\s+maximum\s+number\s+of\s+tokens\b"
)
_MODEL_UNAVAILABLE_MESSAGE_SOURCE = (
    r"(?i)\bmodel\b[^.]{0,80}\b(?:not\s+found|does\s+not\s+exist|not\s+available|unavailable"
    r"|is\s+not\s+supported|has\s+been\s+deprecated|decommissioned)\b"
    r"|\b(?:unknown|invalid|no\s+such)\s+model\b|\bfunction\b[^.]{0,40}\bnot\s+found\b"
)
_VISION_MESSAGE_SOURCE = r"(?i)\b(?:image|images|image_url|vision|visual|multimodal|multi-modal)\b"
_AUDIO_MESSAGE_SOURCE = r"(?i)\b(?:audio|input_audio|speech)\b"
_CAPABILITY_REJECTION_SOURCE = (
    r"(?i)\b(?:model|endpoint)\b[^.]{0,100}\b(?:does\s+not|cannot|can't|only|not)\b"
    r"[^.]{0,60}\b(?:support|accept|process|text)\b"
    r"|\b(?:model|endpoint)\b[^.]{0,100}\bis\s+text[-\s]only\b"
    r"|\b(?:input|inputs|vision|audio)\b[^.]{0,60}\bnot\s+(?:supported|accepted|enabled)\b"
    r"[^.]{0,60}\b(?:model|endpoint)\b"
)
_PARAMETER_NAME_SOURCE = (
    r"(?i)\b(temperature|top_p|top_k|min_p|presence_penalty|frequency_penalty|repetition_penalty"
    r"|max[ _]tokens|max_completion_tokens|max_output_tokens|seed|logprobs|top_logprobs"
    r"|response_format|tool_choice|parallel_tool_calls|reasoning_effort|logit_bias"
    r"|stream_options|service_tier)\b"
)
_REQUEST_STRUCTURE_FIELDS = frozenset(
    (
        "messages",
        "input",
        "prompt",
        "contents",
        "tools",
        "functions",
        "instructions",
        "image",
        "image_url",
        "audio",
        "input_audio",
        "file",
    )
)
_PARAMETER_REFERENCE_SOURCE = (
    r"(?i)(?:unknown|unrecognized|unsupported|unexpected|invalid|extra)\s+(?:request\s+)?"
    r"(?:name|field|parameter|argument|property|key)s?(?:\s+supplied)?\s*[:=]?\s*[\"'`]"
    r"([A-Za-z_][\w.\[\]-]{0,63})[\"'`]|(?:parameter|argument|field|property)\s+[\"'`]"
    r"([A-Za-z_][\w.\[\]-]{0,63})[\"'`]|[\"'`]([A-Za-z_][\w.\[\]-]{0,63})[\"'`]\s+is\s+not\s+"
    r"(?:supported|allowed|permitted|valid)"
)


def _signals(report: OpenAIProviderErrorReport) -> frozenset[str]:
    return frozenset(
        re.sub(r"[\s-]+", "_", value.strip().lower())
        for value in (report.code, report.error_type)
        if value
    )


def _matches(source: str, message: str) -> bool:
    return re.search(source, message) is not None


def _classify_signals(signals: frozenset[str]) -> UpstreamFailureType | None:
    for signal_set, failure_type in (
        (_BILLING_SIGNALS, UpstreamFailureType.BILLING),
        (_AUTHENTICATION_SIGNALS, UpstreamFailureType.AUTHENTICATION),
        (_PERMISSION_SIGNALS, UpstreamFailureType.PERMISSION),
        (_CONTENT_POLICY_SIGNALS, UpstreamFailureType.CONTENT_POLICY),
        (_CONTEXT_LENGTH_SIGNALS, UpstreamFailureType.CONTEXT_LENGTH),
        (_INVALID_PARAMETER_SIGNALS, UpstreamFailureType.INVALID_PARAMETER),
        (_RATE_LIMIT_SIGNALS, UpstreamFailureType.RATE_LIMIT),
        (_MODEL_UNAVAILABLE_SIGNALS, UpstreamFailureType.MODEL_UNAVAILABLE),
        (_TIMEOUT_SIGNALS, UpstreamFailureType.TIMEOUT),
        (_OUTAGE_SIGNALS, UpstreamFailureType.PROVIDER_OUTAGE),
    ):
        if signals & signal_set:
            return failure_type
    return None


def _classify_status(status: int, message: str) -> UpstreamFailureType | None:
    if status == 401:
        return UpstreamFailureType.AUTHENTICATION
    if status == 402 or (status in {403, 429} and _matches(_BILLING_MESSAGE_SOURCE, message)):
        return UpstreamFailureType.BILLING
    if status == 403:
        if _matches(_AUTHENTICATION_MESSAGE_SOURCE, message):
            return UpstreamFailureType.AUTHENTICATION
        if _matches(_CONTENT_POLICY_MESSAGE_SOURCE, message):
            return UpstreamFailureType.CONTENT_POLICY
        return UpstreamFailureType.PERMISSION
    if status == 404:
        return UpstreamFailureType.MODEL_UNAVAILABLE
    if status == 409:
        return UpstreamFailureType.INVALID_REQUEST
    if status == 429:
        return UpstreamFailureType.RATE_LIMIT
    if status in _TIMEOUT_STATUSES:
        return UpstreamFailureType.TIMEOUT
    if status >= 500:
        return UpstreamFailureType.PROVIDER_OUTAGE
    return None


def _rejected_modality(
    message: str, request_payload: Mapping[str, JSONValue] | None
) -> UpstreamFailureType | None:
    if not _matches(_CAPABILITY_REJECTION_SOURCE, message):
        return None
    request_modalities = (
        collect_message_modalities(request_payload.get("messages") or request_payload.get("input"))
        if request_payload is not None
        else None
    )
    if (
        request_modalities is None or OpenAIModality.VISION.value in request_modalities
    ) and _matches(_VISION_MESSAGE_SOURCE, message):
        return UpstreamFailureType.UNSUPPORTED_VISION_REQUEST
    if (
        request_modalities is None or OpenAIModality.AUDIO.value in request_modalities
    ) and _matches(_AUDIO_MESSAGE_SOURCE, message):
        return UpstreamFailureType.UNSUPPORTED_AUDIO_REQUEST
    return None


def resolve_provider_media_problem(
    message: str, request_payload: Mapping[str, JSONValue] | None = None
) -> tuple[str, str] | None:
    modality = (
        "vision"
        if _matches(_VISION_MESSAGE_SOURCE, message)
        else "audio" if _matches(_AUDIO_MESSAGE_SOURCE, message) else None
    )
    if modality is None and request_payload is not None:
        requested_media = set(
            collect_message_modalities(
                request_payload.get("messages") or request_payload.get("input")
            )
        ) & {OpenAIModality.VISION.value, OpenAIModality.AUDIO.value}
        if len(requested_media) == 1:
            modality = next(iter(requested_media))
    if modality is None:
        return None
    for source, reason in (
        (r"(?i)\b(?:format|mime|file\s*type|extension|unsupported\s+encoding)\b", "format"),
        (r"(?i)\b(?:too\s+large|size|dimensions?|resolution|pixels?)\b", "size"),
        (r"(?i)\b(?:decode|decoding|base64|corrupt|malformed|cannot\s+identify)\b", "decoding"),
        (r"(?i)\b(?:fetch|retrieve|retrieval|download|unreachable|url)\b", "retrieval"),
        (r"(?i)\b(?:invalid|bad|unreadable)\s+(?:image|audio|attachment)\b", "unspecified"),
    ):
        if _matches(source, message):
            return modality, reason
    return None


def resolve_rejected_provider_parameter(report: OpenAIProviderErrorReport) -> str | None:
    if report.param is not None:
        return report.param
    message = report.provider_message or ""
    reference = re.search(_PARAMETER_REFERENCE_SOURCE, message)
    if reference is not None:
        return normalize_provider_error_token(next(group for group in reference.groups() if group))
    parameter = re.search(_PARAMETER_NAME_SOURCE, message)
    return parameter.group(1).lower().replace(" ", "_") if parameter is not None else None


def _classify_request_message(
    message: str,
    parameter: str | None,
    request_payload: Mapping[str, JSONValue] | None,
    fallback: UpstreamFailureType = UpstreamFailureType.INVALID_REQUEST,
) -> UpstreamFailureType:
    for source, failure_type in (
        (_BILLING_MESSAGE_SOURCE, UpstreamFailureType.BILLING),
        (_AUTHENTICATION_MESSAGE_SOURCE, UpstreamFailureType.AUTHENTICATION),
        (_PERMISSION_MESSAGE_SOURCE, UpstreamFailureType.PERMISSION),
        (_CONTENT_POLICY_MESSAGE_SOURCE, UpstreamFailureType.CONTENT_POLICY),
        (_RATE_LIMIT_MESSAGE_SOURCE, UpstreamFailureType.RATE_LIMIT),
    ):
        if _matches(source, message):
            return failure_type
    if _matches(_CONTEXT_LENGTH_MESSAGE_SOURCE, message):
        return UpstreamFailureType.CONTEXT_LENGTH
    parameter_root = re.split(r"[.\[]", parameter, maxsplit=1)[0].lower() if parameter else None
    if (
        parameter_root not in {None, _MODEL_PARAM}
        and parameter_root not in _REQUEST_STRUCTURE_FIELDS
        and (
            fallback is UpstreamFailureType.INVALID_REQUEST
            or _matches(_PARAMETER_REFERENCE_SOURCE, message)
            or _matches(_PARAMETER_NAME_SOURCE, message)
        )
    ):
        return UpstreamFailureType.INVALID_PARAMETER
    if resolve_provider_media_problem(message, request_payload) is not None:
        return UpstreamFailureType.INVALID_MEDIA
    rejected_modality = _rejected_modality(message, request_payload)
    if rejected_modality is not None:
        return rejected_modality
    if (
        parameter_root == _MODEL_PARAM and fallback is UpstreamFailureType.INVALID_REQUEST
    ) or _matches(_MODEL_UNAVAILABLE_MESSAGE_SOURCE, message):
        return UpstreamFailureType.MODEL_UNAVAILABLE
    return fallback


def classify_openai_provider_failure(
    status: int,
    report: OpenAIProviderErrorReport,
    request_payload: Mapping[str, JSONValue] | None,
) -> UpstreamFailureType:
    message = report.provider_message or ""
    signals = _signals(report)
    classified_signal = _classify_signals(signals)
    if classified_signal is not None:
        return classified_signal
    if status >= 500 and status not in _TIMEOUT_STATUSES and signals & _INVALID_REQUEST_SIGNALS:
        return _classify_request_message(
            message, resolve_rejected_provider_parameter(report), request_payload
        )
    return _classify_status(status, message) or _classify_request_message(
        message,
        resolve_rejected_provider_parameter(report),
        request_payload,
        fallback=(
            UpstreamFailureType.PROVIDER_OUTAGE
            if status == 0
            else UpstreamFailureType.INVALID_REQUEST
        ),
    )
