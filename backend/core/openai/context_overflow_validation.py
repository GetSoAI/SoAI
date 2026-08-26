"""SoAI - Context overflow validation helpers [backend/core/openai/context_overflow_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.integers import coerce_positive_exact_int_or_none
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CONTEXT_OVERFLOW_CONFIGURATION_GUIDANCE",
    "CONTEXT_OVERFLOW_VALIDATION_TYPE",
    "ContextOverflowValidation",
    "build_context_overflow_validation_error",
    "build_context_overflow_validation_message",
    "extract_context_overflow_validation",
)

CONTEXT_OVERFLOW_VALIDATION_TYPE = "context_window_exceeded"
CONTEXT_OVERFLOW_CONFIGURATION_GUIDANCE = "Increase num_ctx/context_window_tokens, compact the conversation, or select a model with a larger context."
_TOKEN_COUNT_PATTERN = r"[0-9][0-9,._]*"


@dataclass(frozen=True, slots=True)
class ContextOverflowValidation:
    requested_tokens: int
    available_tokens: int
    model: str | None
    configuration_guidance: str = CONTEXT_OVERFLOW_CONFIGURATION_GUIDANCE

    @property
    def message(self) -> str:
        return build_context_overflow_validation_message(
            requested_tokens=self.requested_tokens,
            available_tokens=self.available_tokens,
            model=self.model,
            configuration_guidance=self.configuration_guidance,
        )

    def to_details(self) -> JSONDict:
        details: JSONDict = {
            "type": CONTEXT_OVERFLOW_VALIDATION_TYPE,
            "requested_tokens": int(self.requested_tokens),
            "available_tokens": int(self.available_tokens),
            "configuration_guidance": self.configuration_guidance,
        }
        if self.model is not None:
            details["model"] = self.model
        return details


def build_context_overflow_validation_message(
    *,
    requested_tokens: int,
    available_tokens: int,
    model: str | None,
    configuration_guidance: str = CONTEXT_OVERFLOW_CONFIGURATION_GUIDANCE,
) -> str:
    model_text = ""
    normalized_model = coerce_optional_trimmed_str(model)
    if normalized_model is not None:
        model_text = f" '{normalized_model}'"
    return (
        f"The selected model{model_text} has a {available_tokens:,}-token context, "
        f"but this request needs {requested_tokens:,} tokens. "
        f"{configuration_guidance}"
    )


def build_context_overflow_validation_error(
    provider_message: str,
    *,
    model: str | None = None,
    details: Mapping[str, JSONValue] | None = None,
    code: str | None = None,
) -> ValidationError | None:
    validation = extract_context_overflow_validation(
        provider_message,
        details,
        model=model,
        code=code,
    )
    if validation is None:
        return None
    return ValidationError(
        validation.message,
        details=validation.to_details(),
    )


def extract_context_overflow_validation(
    message: str,
    details: Mapping[str, JSONValue] | None = None,
    *,
    model: str | None = None,
    code: str | None = None,
) -> ContextOverflowValidation | None:
    structured = _extract_from_structured_details(details, model=model)
    if structured is not None:
        return structured
    candidate_messages: list[tuple[str, str | None, str | None]] = []
    candidate_messages.append((message, model, code))
    if isinstance(details, Mapping):
        upstream_message = details.get("upstream_error_message")
        upstream_code = details.get("upstream_error_code")
        upstream_model = details.get("model")
        if isinstance(upstream_message, str) and upstream_message.strip():
            candidate_messages.append(
                (
                    upstream_message,
                    coerce_optional_trimmed_str(upstream_model) or model,
                    str(upstream_code) if upstream_code is not None else code,
                )
            )
    for candidate_message, candidate_model, candidate_code in candidate_messages:
        resolved = _extract_from_message(
            candidate_message,
            model=candidate_model,
            code=candidate_code,
        )
        if resolved is not None:
            return resolved
    return None


def _extract_from_structured_details(
    details: Mapping[str, JSONValue] | None,
    *,
    model: str | None,
) -> ContextOverflowValidation | None:
    if not isinstance(details, Mapping):
        return None
    details_type = coerce_optional_trimmed_str(details.get("type"))
    validation_type = coerce_optional_trimmed_str(details.get("validation_type"))
    if CONTEXT_OVERFLOW_VALIDATION_TYPE not in (details_type, validation_type):
        return None
    requested_tokens = coerce_positive_exact_int_or_none(details.get("requested_tokens"))
    available_tokens = coerce_positive_exact_int_or_none(details.get("available_tokens"))
    if requested_tokens is None or available_tokens is None or requested_tokens <= available_tokens:
        return None
    configured_model = coerce_optional_trimmed_str(details.get("model")) or model
    guidance = (
        coerce_optional_trimmed_str(details.get("configuration_guidance"))
        or CONTEXT_OVERFLOW_CONFIGURATION_GUIDANCE
    )
    return ContextOverflowValidation(
        requested_tokens=requested_tokens,
        available_tokens=available_tokens,
        model=configured_model,
        configuration_guidance=guidance,
    )


def _extract_from_message(
    message: str,
    *,
    model: str | None,
    code: str | None,
) -> ContextOverflowValidation | None:
    normalized_message = message.strip()
    normalized_code = coerce_optional_trimmed_str(code)
    if not normalized_message:
        return None
    split_counts = _extract_split_input_output_counts(
        normalized_message,
        model=model,
    )
    if split_counts is not None:
        return split_counts
    for pattern in _build_message_patterns():
        match = pattern.search(normalized_message)
        if match is None:
            continue
        requested_tokens = _parse_token_count(match.group("requested"))
        available_tokens = _parse_token_count(match.group("available"))
        if requested_tokens is None or available_tokens is None:
            return None
        if requested_tokens <= available_tokens:
            return None
        resolved_model = coerce_optional_trimmed_str(match.groupdict().get("model")) or model
        return ContextOverflowValidation(
            requested_tokens=requested_tokens,
            available_tokens=available_tokens,
            model=resolved_model,
        )
    if normalized_code != "context_length_exceeded":
        return None
    return None


def _extract_split_input_output_counts(
    message: str,
    *,
    model: str | None,
) -> ContextOverflowValidation | None:
    match = re.search(
        rf"maximum\s+context\s+length\s+is\s+(?P<available>{_TOKEN_COUNT_PATTERN})\s+tokens?.*?requested\s+(?P<output>{_TOKEN_COUNT_PATTERN})\s+output\s+tokens?.*?prompt\s+contains\s+at\s+least\s+(?P<input>{_TOKEN_COUNT_PATTERN})\s+input\s+tokens?",
        message,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None
    available_tokens = _parse_token_count(match.group("available"))
    output_tokens = _parse_token_count(match.group("output"))
    input_tokens = _parse_token_count(match.group("input"))
    if available_tokens is None or output_tokens is None or input_tokens is None:
        return None
    requested_tokens = input_tokens + output_tokens
    if requested_tokens <= available_tokens:
        return None
    return ContextOverflowValidation(
        requested_tokens=requested_tokens,
        available_tokens=available_tokens,
        model=model,
    )


def _parse_token_count(value: str | None) -> int | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace(",", "").replace("_", "").replace(".", "")
    return coerce_positive_exact_int_or_none(normalized, allow_signed_text=False)


def _build_message_patterns() -> tuple[re.Pattern[str], ...]:
    return (
        re.compile(
            rf"request\s*\(?(?P<requested>{_TOKEN_COUNT_PATTERN})\s+tokens\)?\s+exceeds\s+(?:the\s+)?available\s+context\s+size\s*\(?(?P<available>{_TOKEN_COUNT_PATTERN})(?:\s+tokens?)?\)?",
            re.IGNORECASE,
        ),
        re.compile(
            rf"maximum\s+context\s+length\s+is\s+(?P<available>{_TOKEN_COUNT_PATTERN})\s+tokens?.*?requested\s+(?P<requested>{_TOKEN_COUNT_PATTERN})\s+tokens?",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            rf"requested\s+tokens?\s*\(?(?P<requested>{_TOKEN_COUNT_PATTERN})\)?\s+exceed(?:s|ed)?\s+(?:the\s+)?context\s+(?:window|length|size)\s+(?:of\s+)?(?P<available>{_TOKEN_COUNT_PATTERN})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"requested\s+(?P<requested>{_TOKEN_COUNT_PATTERN})\s+tokens?.*?context\s+(?:window|length|size)\s+(?:is|of)\s+(?P<available>{_TOKEN_COUNT_PATTERN})",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            rf"The selected model(?: '(?P<model>[^']+)')? has a (?P<available>{_TOKEN_COUNT_PATTERN})-token context, but this request needs (?P<requested>{_TOKEN_COUNT_PATTERN}) tokens\.",
            re.IGNORECASE,
        ),
    )
