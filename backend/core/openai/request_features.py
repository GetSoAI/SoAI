"""SoAI - OpenAI request feature extraction helpers [backend/core/openai/request_features.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.validation.boolean_coercion import coerce_payload_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "coerce_stream_requested",
    "extract_usage_reporting_requested",
    "request_includes_tool_calling",
)

LOGGER_NAME = "SoAI.core.openai.request_features"


def coerce_stream_requested(
    payload: JSONDict,
    *,
    logger: TraceLogger,
    operation: str,
    default: bool = False,
) -> bool:
    return coerce_payload_bool(
        payload.get("stream", default),
        logger=logger,
        operation=operation,
        default=default,
    )


def extract_usage_reporting_requested(payload: JSONDict) -> bool:
    stream_options = payload.get("stream_options")
    if not isinstance(stream_options, dict):
        return False
    include_usage = stream_options.get("include_usage")
    return include_usage is True


def request_includes_tool_calling(payload: JSONDict) -> tuple[bool, int]:
    tools_value = payload.get("tools")
    tools_count = 0
    if isinstance(tools_value, list):
        tools_count = len(tools_value)
        if tools_count > 0:
            return (True, tools_count)
    tool_choice = payload.get("tool_choice")
    if isinstance(tool_choice, dict):
        return (True, tools_count)
    if isinstance(tool_choice, str):
        normalized = tool_choice.strip().lower()
        if normalized not in {"", "none", "auto"}:
            return (True, tools_count)
    if coerce_payload_bool(
        payload.get("parallel_tool_calls"),
        logger=get_logger(LOGGER_NAME),
        operation="core.openai.request_features.coerce_payload_bool",
        default=False,
        recover_message="Failed to parse boolean from payload (non-critical).",
    ):
        return (True, tools_count)
    return (False, tools_count)
