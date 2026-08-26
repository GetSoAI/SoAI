"""SoAI - OpenAI chat inference payload post-processing [backend/features/api/routes/openai/chat/inference_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal

from fastapi.responses import JSONResponse

from core.logging.trace import get_logger
from core.openai.content_text_rendering import render_openai_content_text
from core.openai.tool_calls import extract_tool_calls_from_payload
from core.runtime.request_context import RequestContext
from core.tasks.task import Task
from core.validation.integers import is_strict_int
from features.api.runtime.openai_context.internal_protocols import (
    OpenAIApiContextProtocol,
)
from features.api.runtime.responses import create_json_response_with_task_id

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("handle_inference_payload_response",)

LOGGER_NAME = "SoAI.features.api.inference_payload"


def _resolve_completion_choice_text(choice: Mapping[str, JSONValue]) -> str:
    text_value = choice.get("text")
    if isinstance(text_value, str):
        return text_value
    message_value = choice.get("message")
    if isinstance(message_value, Mapping):
        return render_openai_content_text(message_value.get("content"))
    return render_openai_content_text(text_value)


def _coerce_text_completion_payload(payload: Mapping[str, JSONValue]) -> JSONDict:
    payload_dict: JSONDict = dict(payload)
    choices_value = payload_dict.get("choices")
    if not isinstance(choices_value, list):
        payload_dict["object"] = "text_completion"
        return payload_dict
    coerced_choices: list[JSONDict] = []
    for fallback_index, choice_value in enumerate(choices_value):
        if not isinstance(choice_value, Mapping):
            return payload_dict
        index_value = choice_value.get("index")
        index = int(index_value) if is_strict_int(index_value) else fallback_index
        logprobs = choice_value.get("logprobs") if "logprobs" in choice_value else None
        finish_reason = (
            choice_value.get("finish_reason") if "finish_reason" in choice_value else None
        )
        coerced_choices.append(
            {
                "index": index,
                "text": _resolve_completion_choice_text(choice_value),
                "logprobs": logprobs,
                "finish_reason": finish_reason,
            }
        )
    payload_dict["object"] = "text_completion"
    payload_dict["choices"] = coerced_choices
    return payload_dict


async def handle_inference_payload_response(
    api_context: OpenAIApiContextProtocol,
    context: RequestContext,
    payload: Mapping[str, JSONValue],
    task: Task,
    response_format: Literal["chat", "completions"] = "chat",
) -> JSONResponse:
    payload_dict = (
        _coerce_text_completion_payload(payload)
        if response_format == "completions"
        else dict(payload)
    )
    logger = get_logger(LOGGER_NAME)
    tool_calls = extract_tool_calls_from_payload(payload_dict)
    if tool_calls:
        logger.info("Response tool calls: %s", len(tool_calls))
    if tool_calls:
        track_background_task = api_context.dependencies.application_control.track_background_task
        api_context.dependencies.tool_call_processor.schedule_tool_call_processing(
            request_context=context,
            raw_tool_calls=tool_calls,
            logger=logger,
            track_background_task=track_background_task,
        )
    return create_json_response_with_task_id(
        payload_dict,
        task.task_id,
        operation_id=context.trace_id,
    )
