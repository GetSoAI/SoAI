"""SoAI - OpenAI capability requirement inference [backend/core/openai/capability_requirements.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.openai.capability_taxonomy import OpenAIChatFeature, OpenAIModality
from core.openai.modalities import collect_message_modalities
from core.types.json import JSONDict
from core.validation.boolean_coercion import coerce_payload_bool
from core.validation.string_sequences import normalize_string_sequence

__all__ = (
    "augment_openai_capability_requirements",
    "infer_responses_capability_requirements",
)

LOGGER_NAME = "SoAI.core.openai.capability_requirements"


def augment_openai_capability_requirements(
    base_capabilities: tuple[str, ...],
    payload: JSONDict,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    capabilities: list[str] = list(base_capabilities)
    modalities = list(collect_message_modalities(payload.get("messages")))

    def append_capability(value: str) -> None:
        if value and value not in capabilities:
            capabilities.append(value)

    if OpenAIModality.VISION.value in modalities:
        append_capability(OpenAIChatFeature.VISION.value)
    if OpenAIModality.AUDIO.value in modalities:
        append_capability(OpenAIChatFeature.INPUT_AUDIO.value)
    tools_value = payload.get("tools")
    if isinstance(tools_value, list) and tools_value:
        append_capability(OpenAIChatFeature.TOOL_CALLING.value)
    tool_choice = payload.get("tool_choice")
    if isinstance(tool_choice, dict):
        append_capability(OpenAIChatFeature.TOOL_CALLING.value)
    elif isinstance(tool_choice, str):
        normalized_choice = tool_choice.strip().lower()
        if normalized_choice not in {"", "none", "auto"}:
            append_capability(OpenAIChatFeature.TOOL_CALLING.value)
    if coerce_payload_bool(
        payload.get("parallel_tool_calls"),
        logger=get_logger(LOGGER_NAME),
        operation="core.openai.capability_requirements.coerce_payload_bool",
        default=False,
    ):
        append_capability(OpenAIChatFeature.PARALLEL_TOOL_CALLS.value)
    response_format = payload.get("response_format")
    if isinstance(response_format, dict):
        format_type = str(response_format.get("type", "")).strip().lower()
        if format_type and format_type != "text":
            append_capability(OpenAIChatFeature.STRUCTURED_OUTPUT.value)
            if format_type == "json_schema":
                append_capability(OpenAIChatFeature.JSON_SCHEMA.value)
    json_schema_value = payload.get("json_schema")
    if isinstance(json_schema_value, dict) or coerce_payload_bool(
        json_schema_value,
        logger=get_logger(LOGGER_NAME),
        operation="core.openai.capability_requirements.coerce_payload_bool",
        default=False,
    ):
        append_capability(OpenAIChatFeature.STRUCTURED_OUTPUT.value)
        append_capability(OpenAIChatFeature.JSON_SCHEMA.value)
    return (
        normalize_string_sequence(capabilities),
        normalize_string_sequence(modalities),
    )


def infer_responses_capability_requirements(payload: JSONDict) -> tuple[str, ...]:
    capabilities: list[str] = []
    has_tooling = False

    def append_capability(value: str) -> None:
        if value and value not in capabilities:
            capabilities.append(value)

    tools_value = payload.get("tools")
    if isinstance(tools_value, list) and tools_value:
        has_tooling = True
        append_capability(OpenAIChatFeature.TOOL_CALLING.value)
    tool_choice_value = payload.get("tool_choice")
    if isinstance(tool_choice_value, dict):
        has_tooling = True
        append_capability(OpenAIChatFeature.TOOL_CALLING.value)
    elif isinstance(tool_choice_value, str):
        normalized_choice = tool_choice_value.strip().lower()
        if normalized_choice and normalized_choice != "none":
            has_tooling = True
            append_capability(OpenAIChatFeature.TOOL_CALLING.value)
    elif tool_choice_value is not None:
        has_tooling = True
        append_capability(OpenAIChatFeature.TOOL_CALLING.value)

    if has_tooling and payload.get("parallel_tool_calls") is True:
        append_capability(OpenAIChatFeature.TOOL_CALLING.value)
        append_capability(OpenAIChatFeature.PARALLEL_TOOL_CALLS.value)

    text_value = payload.get("text")
    if isinstance(text_value, dict):
        format_value = text_value.get("format")
        if isinstance(format_value, dict):
            format_type = str(format_value.get("type", "")).strip().lower()
            if format_type and format_type != "text":
                append_capability(OpenAIChatFeature.STRUCTURED_OUTPUT.value)
            if format_type == "json_schema":
                append_capability(OpenAIChatFeature.STRUCTURED_OUTPUT.value)
                append_capability(OpenAIChatFeature.JSON_SCHEMA.value)

    return normalize_string_sequence(capabilities)
