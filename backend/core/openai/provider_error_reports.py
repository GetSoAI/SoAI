"""SoAI - Upstream provider error body normalization [backend/core/openai/provider_error_reports.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.security.public_text_redaction import (
    redact_public_text_fragments,
    sanitize_public_diagnostic_text,
)
from core.security.sensitive_detection import looks_like_sensitive_string
from core.serialization.json_parsing import parse_json_value_or_none
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "OpenAIProviderErrorReport",
    "extract_openai_provider_error_report",
    "normalize_provider_error_token",
    "normalize_provider_request_reference",
)

_PROVIDER_MESSAGE_MAX_LENGTH = 4000
_TOKEN_PATTERN_SOURCE = r"[A-Za-z0-9_.:/\[\]-]{1,128}"
_REQUEST_REFERENCE_PATTERN_SOURCE = r"[A-Za-z0-9_.:-]{1,128}"
_IGNORED_PROBLEM_TYPES = frozenset({"about:blank"})


@dataclass(frozen=True, slots=True)
class OpenAIProviderErrorReport:
    provider_message: str | None
    explanation: str | None
    error_type: str | None
    code: str | None
    param: str | None


def normalize_provider_error_token(value: JSONValue) -> str | None:
    if is_strict_int(value):
        return str(value)
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or not re.fullmatch(_TOKEN_PATTERN_SOURCE, candidate):
        return None
    if candidate.lower() in _IGNORED_PROBLEM_TYPES or looks_like_sensitive_string(candidate):
        return None
    return candidate


def normalize_provider_request_reference(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or not re.fullmatch(_REQUEST_REFERENCE_PATTERN_SOURCE, candidate):
        return None
    return None if looks_like_sensitive_string(candidate) else candidate


def _first_text(*values: JSONValue) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_token(*values: JSONValue) -> str | None:
    for value in values:
        token = normalize_provider_error_token(value)
        if token is not None:
            return token
    return None


def _first_code(*values: JSONValue) -> str | None:
    return _first_token(*(value for value in values if isinstance(value, str))) or _first_token(
        *values
    )


def _validation_location(entry: Mapping[str, JSONValue]) -> str | None:
    location = entry.get("loc")
    if isinstance(location, list):
        parts = [
            str(part)
            for part in location
            if (isinstance(part, str) or is_strict_int(part)) and part != "body"
        ]
        return normalize_provider_error_token(".".join(parts)) if parts else None
    return normalize_provider_error_token(entry.get("field"))


def _validation_entries(value: JSONValue) -> list[Mapping[str, JSONValue]]:
    if not isinstance(value, list):
        return []
    entries: list[Mapping[str, JSONValue]] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        entries.append(entry)
        entries.extend(_validation_entries(entry.get("fieldViolations")))
    return entries


def _validation_details(
    value: JSONValue, known_message: str | None
) -> tuple[str | None, str | None]:
    messages: list[str] = []
    first_param: str | None = None
    for entry in _validation_entries(value):
        message = _first_text(entry.get("msg"), entry.get("message"), entry.get("description"))
        if message is None:
            continue
        location = _validation_location(entry)
        if first_param is None:
            first_param = location
        if known_message is None or message not in known_message:
            messages.append(f"{location}: {message}" if location else message)
    return ("; ".join(messages) or None, first_param)


def _error_reasons(value: JSONValue) -> list[JSONValue]:
    return [entry.get("reason") for entry in _validation_entries(value)]


def _mapping(value: JSONValue) -> Mapping[str, JSONValue]:
    return value if isinstance(value, Mapping) else {}


def _unwrap_payload(payload: JSONValue) -> JSONValue:
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], Mapping):
        return payload[0]
    return payload


def extract_openai_provider_error_report(
    payload: JSONValue,
    *,
    body_text: str | None = None,
) -> OpenAIProviderErrorReport:
    if payload is None:
        payload = parse_json_value_or_none(body_text, field="provider error body")
    payload = _unwrap_payload(payload)
    if not isinstance(payload, Mapping):
        message = _first_text(payload, body_text)
        return _build_report(message, error_type=None, code=None, param=None)
    error_object = _mapping(payload.get("error"))
    nested_message = _mapping(error_object.get("message") or payload.get("message"))
    message = _first_text(
        error_object.get("message"),
        payload.get("error"),
        payload.get("message"),
        payload.get("detail"),
    )
    validation_message, validation_param = _validation_details(
        error_object.get("details") or nested_message.get("detail") or payload.get("detail"),
        message,
    )
    message = " ".join(part for part in (message, validation_message) if part) or _first_text(
        payload.get("title")
    )
    return _build_report(
        message,
        error_type=_first_token(
            error_object.get("type"),
            error_object.get("status"),
            payload.get("type"),
            payload.get("title"),
        ),
        code=_first_code(
            error_object.get("code"),
            *_error_reasons(error_object.get("details")),
            payload.get("code"),
            payload.get("status"),
        ),
        param=_first_token(error_object.get("param"), payload.get("param"), validation_param),
    )


def _build_report(
    message: str | None,
    *,
    error_type: str | None,
    code: str | None,
    param: str | None,
) -> OpenAIProviderErrorReport:
    provider_message = (
        redact_public_text_fragments(message)[:_PROVIDER_MESSAGE_MAX_LENGTH] if message else None
    )
    return OpenAIProviderErrorReport(
        provider_message=provider_message,
        explanation=sanitize_public_diagnostic_text(message),
        error_type=error_type,
        code=code,
        param=param,
    )
