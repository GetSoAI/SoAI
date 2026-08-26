"""SoAI - OpenAI Responses endpoint cancel handler [backend/features/api/routes/openai/responses/endpoint_family_cancel.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

from fastapi import Depends, Request
from starlette.responses import Response

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.openai.response_terminal_policy import is_terminal_response_status
from core.tasks.enums import TaskStatus
from core.tasks.task_cancellation import cancel
from features.api.openai.openai_error_responses import build_openai_error_json_response
from features.api.routes.openai.responses.endpoint_family_record_loading import (
    extract_stored_response_json_or_error,
    fetch_owned_response_record_for_request_or_error,
)
from features.api.routes.openai.responses.endpoint_family_response_shared import (
    create_response_not_found_error,
    response_record_flag_enabled,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.response_body import create_json_body_response
from features.api.runtime.responses import apply_operation_id_header

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.endpoint_family_cancel"
OPERATION = "openai.responses.cancel"


def register_routes(routers: ApiRouters) -> None:
    router = routers.openai_public
    common_tags: list[str | Enum] = ["OpenAI Responses"]
    common_deps = [openai_api_dependency()]
    router.post(
        "/responses/{response_id}/cancel",
        tags=common_tags,
        dependencies=common_deps,
    )(cancel_response)


async def cancel_response(
    response_id: str,
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    trace_id = request.state.context.trace_id
    owned_record = await fetch_owned_response_record_for_request_or_error(
        request,
        api_context,
        response_id=response_id,
        require_stored=True,
    )
    if isinstance(owned_record, Response):
        return owned_record
    normalized_response_id, record, requesting_api_key_id, requesting_user_id = owned_record
    if not response_record_flag_enabled(record, "is_background"):
        return build_openai_error_json_response(
            status_code=400,
            message="Only background responses can be cancelled.",
            canonical_error_type="invalid_request_error",
            param=None,
            code=None,
            trace_id=trace_id,
            headers=None,
        )
    task_id_value = record.get("task_id")
    task_id = task_id_value if isinstance(task_id_value, str) and task_id_value else ""
    if not task_id:
        return build_openai_error_json_response(
            status_code=502,
            message="Stored response is missing task_id.",
            canonical_error_type="server_error",
            param=None,
            code=None,
            trace_id=trace_id,
            headers=None,
        )
    response_json = extract_stored_response_json_or_error(record, trace_id=trace_id)
    if isinstance(response_json, Response):
        return response_json
    response_status_value = response_json.get("status")
    response_status = (
        response_status_value.strip().lower() if isinstance(response_status_value, str) else ""
    )
    if is_terminal_response_status(response_status):
        return apply_operation_id_header(create_json_body_response(content=response_json), trace_id)
    try:
        canceled_task = await cancel(
            api_context.dependencies.task_registry,
            task_id,
            reason="OpenAI Responses cancel requested.",
            context=request.state.context,
        )
        if canceled_task is None:
            return build_openai_error_json_response(
                status_code=502,
                message="Response task is no longer available.",
                canonical_error_type="server_error",
                param=None,
                code=None,
                trace_id=trace_id,
                headers=None,
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation="openai.responses.cancel")
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed cancelling response task.",
            trace_id=request.state.context.trace_id,
            operation=OPERATION,
            level="warning",
        )
        return apply_operation_id_header(
            build_openai_error_json_response(
                status_code=502,
                message="Failed to cancel response task.",
                canonical_error_type="server_error",
                param=None,
                code=None,
                trace_id=trace_id,
                headers=None,
            ),
            trace_id,
        )
    persisted = await api_context.dependencies.database_openai_responses.get_response(
        response_id=normalized_response_id,
        user_id=requesting_user_id,
        api_key_id=requesting_api_key_id,
    )
    if persisted is None:
        return create_response_not_found_error(trace_id=trace_id)
    persisted_status_value = persisted.get("status")
    persisted_status = (
        persisted_status_value.strip().lower() if isinstance(persisted_status_value, str) else ""
    )
    cancellation_in_progress = (
        canceled_task.status == TaskStatus.CANCELLED or not canceled_task.status.is_terminal()
    )
    if cancellation_in_progress and not is_terminal_response_status(persisted_status):
        persisted["status"] = "cancelling"
    return apply_operation_id_header(create_json_body_response(content=persisted), trace_id)
