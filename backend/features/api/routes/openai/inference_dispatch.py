"""SoAI - Shared OpenAI inference request dispatch handler [backend/features/api/routes/openai/inference_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request
from pydantic import BaseModel
from starlette.responses import Response

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_models_requests import InferenceRequestReceived
from core.logging.trace import get_logger
from core.timing.monotonic import monotonic_ms
from features.api.routes.openai.chat.inference_request import handle_inference_request
from features.api.runtime.chat_execution.preparation import (
    prepare_openai_chat_execution,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.openai_error_conversion import (
    build_openai_http_exception_response,
    build_openai_internal_error_response,
    build_openai_soai_error_response,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("handle_generic_inference_endpoint",)

OPERATION_FEATURES_API_ROUTES_OPENAI_INFERENCE_DISPATCH_HANDLE_GENERIC_INFERENCE_ENDPOINT = (
    "features.api.routes.openai.inference_dispatch.handle_generic_inference_endpoint"
)


LOGGER_NAME = "SoAI.features.api.inference_dispatch"


async def handle_generic_inference_endpoint(
    request: Request,
    api_context: ApiContext,
    request_event_class: type[InferenceRequestReceived],
    metric_counter_key: str,
    payload: BaseModel,
    base_capabilities: tuple[str, ...] = (),
    request_json_preprocessor: (
        Callable[[ApiContext, JSONDict], Awaitable[None] | None] | None
    ) = None,
) -> Response:
    context = request.state.context
    metrics_manager = api_context.dependencies.metrics_manager
    start_time_ms = monotonic_ms()
    try:
        prepared_execution = await prepare_openai_chat_execution(
            request=request,
            api_context=api_context,
            request_event_class=request_event_class,
            payload=payload,
            base_capabilities=base_capabilities,
            request_json_preprocessor=request_json_preprocessor,
        )
        if isinstance(prepared_execution, Response):
            return prepared_execution
        metrics_manager.increment_counter("api", "openai", metric_counter_key)
        return await handle_inference_request(
            request=request,
            api_context=api_context,
            prepared_execution=prepared_execution,
        )
    except HTTPException as http_exc:
        metrics_manager.increment_counter("api", "openai", "requests_failed")
        return build_openai_http_exception_response(http_exc, trace_id=context.trace_id)
    except SoAIError as exception:
        metrics_manager.increment_counter("api", "openai", "requests_failed")
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message=f"Request failed in {metric_counter_key} endpoint.",
            trace_id=context.trace_id,
            operation=OPERATION_FEATURES_API_ROUTES_OPENAI_INFERENCE_DISPATCH_HANDLE_GENERIC_INFERENCE_ENDPOINT,
            level="error",
        )
        return build_openai_soai_error_response(exception, trace_id=context.trace_id)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        metrics_manager.increment_counter("api", "openai", "requests_failed")
        coerced = coerce_to_soai_error(
            exception,
            operation=f"api_openai.endpoint.{metric_counter_key}",
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message=f"Unhandled error in {metric_counter_key} endpoint.",
            trace_id=context.trace_id,
            operation=OPERATION_FEATURES_API_ROUTES_OPENAI_INFERENCE_DISPATCH_HANDLE_GENERIC_INFERENCE_ENDPOINT,
            level="error",
        )
        return build_openai_internal_error_response(trace_id=context.trace_id)
    finally:
        metrics_manager.record_timing(
            "api",
            "openai",
            "timings",
            "request_latency_ms",
            duration_ms=float(monotonic_ms() - start_time_ms),
        )
