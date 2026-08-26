"""SoAI - WebSocket model test stream request preparation [backend/features/api/routes/system/events/websocket_model_test_stream/request_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.protocols import LoggerProtocol
from core.openai.request_fields import resolve_optional_model_name
from core.openai.stream_request_preparation import (
    OPENAI_STREAM_FORBIDDEN_FIELDS_WITH_MESSAGES,
    build_openai_stream_request_json,
)
from core.timing.monotonic import monotonic_ms
from features.api.routes.system.events.websocket_model_test_stream.state import (
    ModelTestStreamRuntime,
    publish_model_test_stream_event,
    publish_model_test_stream_loading_error,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "PreparedModelTestStreamRequest",
    "build_model_test_stream_request_json",
    "prepare_model_test_stream_request",
    "publish_model_test_start_error",
)

OPERATION_MODEL_TEST_STREAM_START_MODEL = "model_test_stream.start.model"


@dataclass(frozen=True, slots=True)
class PreparedModelTestStreamRequest:
    request_json: JSONDict


def build_model_test_stream_request_json(
    *,
    openai_request: JSONDict,
    logger: LoggerProtocol,
    trace_id: str | None,
) -> JSONDict:
    return build_openai_stream_request_json(
        openai_request=openai_request,
        logger=logger,
        trace_id=trace_id,
        forbidden_fields=OPENAI_STREAM_FORBIDDEN_FIELDS_WITH_MESSAGES,
        conv_id=None,
        messages=None,
    )


async def prepare_model_test_stream_request(
    *,
    request_json: JSONDict,
    run_id: str,
    user_id: int,
    trace_id: str | None,
    logger: LoggerProtocol,
    api_context: ApiContext,
) -> PreparedModelTestStreamRequest | None:
    model_id = resolve_optional_model_name(request_json)
    if model_id is None:
        log_handled_exception(
            logger,
            ValidationError("WebSocket model test stream requires a model."),
            message="Invalid WebSocket model test stream model id (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_MODEL_TEST_STREAM_START_MODEL,
            level="debug",
        )
        await publish_model_test_start_error(
            api_context=api_context,
            run_id=run_id,
            user_id=user_id,
            message="WebSocket model test stream requires a model.",
            code="invalid_request_error",
        )
        return None
    return PreparedModelTestStreamRequest(request_json=request_json)


async def publish_model_test_start_error(
    *,
    api_context: ApiContext,
    run_id: str,
    user_id: int,
    message: str,
    code: str,
) -> None:
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id or user_id <= 0:
        return
    started_at_ms = monotonic_ms()
    runtime = ModelTestStreamRuntime(
        run_id=normalized_run_id,
        user_id=user_id,
        started_at_ms=started_at_ms,
    )
    await publish_model_test_stream_loading_error(
        api_context.dependencies.event_bus,
        runtime,
        started_at_ms=started_at_ms,
        duration_ms=0,
        reason=None,
        error_type=code,
    )
    await publish_model_test_stream_event(
        api_context.dependencies.event_bus,
        runtime,
        event_type="error",
        payload={"message": message, "code": code},
    )
