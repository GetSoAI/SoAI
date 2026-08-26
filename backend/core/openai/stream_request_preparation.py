"""SoAI - OpenAI stream request JSON preparation helpers [backend/core/openai/stream_request_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.inference_normalization import normalize_openai_inference_payload
from core.openai.request_field_validation import (
    reject_unsupported_openai_request_fields,
)
from core.types.json_value import copy_json_dict, copy_json_dict_list

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("build_openai_stream_request_json",)

OPENAI_STREAM_FORBIDDEN_FIELDS_WITH_MESSAGES: tuple[str, ...] = (
    "conv_id",
    "function_call",
    "functions",
    "parallel_tool_calls",
    "tool_choice",
    "tools",
)

OPENAI_STREAM_FORBIDDEN_FIELDS_WITHOUT_MESSAGES: tuple[str, ...] = (
    *OPENAI_STREAM_FORBIDDEN_FIELDS_WITH_MESSAGES,
    "messages",
    "stream",
)


def build_openai_stream_request_json(
    *,
    openai_request: JSONDict,
    logger: LoggerProtocol,
    trace_id: str | None,
    forbidden_fields: tuple[str, ...],
    conv_id: str | None = None,
    messages: list[JSONDict] | None = None,
) -> JSONDict:
    reject_unsupported_openai_request_fields(
        openai_request,
        forbidden_fields=forbidden_fields,
        trace_id=trace_id,
    )
    request_json = copy_json_dict(openai_request)
    request_json["stream"] = True
    if conv_id is not None:
        request_json["conv_id"] = conv_id
    if messages is not None:
        request_json["messages"] = copy_json_dict_list(messages)
    normalized = normalize_openai_inference_payload(
        request_json,
        logger=logger,
        trace_id=trace_id or "ws",
        filter_request_fields=False,
    )
    return normalized.payload
