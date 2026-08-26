"""SoAI - Orchestrator execution event context extraction [backend/orchestrator/execution/event_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext, create_system_context
from core.serialization.json import normalize_for_json
from core.tasks.orchestration_context import OrchestrationContext
from core.types.json_value import coerce_json_dict
from core.validation.booleans import parse_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "extract_event_context_as_dict",
    "is_streaming_request",
    "resolve_event_context",
)

LOGGER_NAME = "SoAI.orchestrator.execution.event_context"
OPERATION = "orchestrator.execution.event_context.is_streaming_request"
STREAM_FLAG_PARSE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)


def extract_event_context_as_dict(
    context: OrchestrationContext,
) -> JSONDict:
    event = context.event
    if event is None:
        return {}
    event_context = event.context
    if not isinstance(event_context, RequestContext):
        raise StateError("OrchestrationContext event.context is invalid.")
    normalized = normalize_for_json(asdict(event_context))
    coerced = coerce_json_dict(normalized)
    return coerced or {}


def resolve_event_context(
    context: OrchestrationContext,
    default_context_name: str,
) -> RequestContext:
    event = context.event
    if event is None:
        return create_system_context(default_context_name)
    event_context = event.context
    if not isinstance(event_context, RequestContext):
        raise StateError("OrchestrationContext event.context is invalid.")
    return event_context


def is_streaming_request(context: OrchestrationContext) -> bool:
    event = context.event
    if event is None:
        return False
    payload = event.payload
    stream_value = payload.get("stream", False)
    try:
        return bool(parse_bool(stream_value, default=False))
    except STREAM_FLAG_PARSE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to parse streaming flag from event payload (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return False
