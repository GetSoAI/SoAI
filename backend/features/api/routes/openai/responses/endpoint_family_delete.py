"""SoAI - OpenAI Responses endpoint delete handler [backend/features/api/routes/openai/responses/endpoint_family_delete.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

from fastapi import Depends, Request
from starlette.responses import Response

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.task_cancellation import cancel
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from core.types.json import JSONDict
from features.api.routes.openai.responses.endpoint_family_record_loading import (
    fetch_owned_response_record_for_request_or_error,
)
from features.api.routes.openai.responses.endpoint_family_response_shared import (
    create_response_not_found_error,
    create_response_server_error,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.response_body import create_json_body_response
from features.api.runtime.responses import apply_operation_id_header

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.endpoint_family_delete"
OPERATION = "openai.responses.delete"


def register_routes(routers: ApiRouters) -> None:
    router = routers.openai_public
    common_tags: list[str | Enum] = ["OpenAI Responses"]
    common_deps = [openai_api_dependency()]
    router.delete(
        "/responses/{response_id}",
        tags=common_tags,
        dependencies=common_deps,
    )(delete_response)


async def delete_response(
    response_id: str,
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    owned_record = await fetch_owned_response_record_for_request_or_error(
        request=request,
        api_context=api_context,
        require_stored=True,
        response_id=response_id,
    )
    if isinstance(owned_record, Response):
        return owned_record
    normalized_response_id, record, requesting_api_key_id, requesting_user_id = owned_record
    trace_id = request.state.context.trace_id
    settlement_error = await _settle_response_task_before_delete(
        request=request,
        api_context=api_context,
        record=record,
    )
    if settlement_error is not None:
        return settlement_error
    try:
        deleted = await api_context.dependencies.database_openai_responses.delete_response(
            response_id=normalized_response_id,
            user_id=requesting_user_id,
            api_key_id=requesting_api_key_id,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        _log_delete_failure(
            exception=exception,
            trace_id=trace_id,
            message="Failed physically deleting response.",
        )
        return _delete_failure_response(
            trace_id=trace_id,
            message="Response storage could not be deleted.",
        )
    if not deleted:
        return create_response_not_found_error(trace_id=trace_id)
    return apply_operation_id_header(
        create_json_body_response(
            content={
                "id": normalized_response_id,
                "object": "response",
                "deleted": True,
            },
        ),
        trace_id,
    )


async def _settle_response_task_before_delete(
    *,
    request: Request,
    api_context: ApiContext,
    record: JSONDict,
) -> Response | None:
    task_id_value = record.get("task_id")
    task_id = task_id_value if isinstance(task_id_value, str) else ""
    if not task_id:
        return _delete_failure_response(
            trace_id=request.state.context.trace_id,
            message="Stored response is missing task ownership.",
        )
    try:
        task = await api_context.dependencies.task_registry.get(task_id, force_refresh=True)
        if task is None or task.status.is_terminal():
            return None
        cancelled_task = await cancel(
            api_context.dependencies.task_registry,
            task_id,
            reason="OpenAI Responses delete requested.",
            context=request.state.context,
        )
        if cancelled_task is None:
            return None
        terminal_task = await api_context.dependencies.task_registry.wait_for_completion(
            task_id,
            timeout=float(INTERACTIVE_TIMEOUT_SEC),
        )
        if terminal_task is not None and terminal_task.status.is_terminal():
            return None
        return _delete_failure_response(
            trace_id=request.state.context.trace_id,
            message="Response task did not reach a terminal state; deletion was not performed.",
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        _log_delete_failure(
            exception=exception,
            trace_id=request.state.context.trace_id,
            message="Failed settling response task before deletion.",
        )
        return _delete_failure_response(
            trace_id=request.state.context.trace_id,
            message="Response task could not be stopped; deletion was not performed.",
        )


def _log_delete_failure(*, exception: Exception, trace_id: str, message: str) -> None:
    coerced = coerce_to_soai_error(exception, operation=OPERATION)
    log_exception(
        get_logger(LOGGER_NAME),
        coerced,
        message=message,
        trace_id=trace_id,
        operation=OPERATION,
        level="warning",
    )


def _delete_failure_response(*, trace_id: str, message: str) -> Response:
    return apply_operation_id_header(
        create_response_server_error(trace_id=trace_id, message=message),
        trace_id,
    )
