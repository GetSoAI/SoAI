"""SoAI - WebUI draft knowledge attachment delete route [backend/features/api/routes/webui/conversation_attachments/knowledge_delete_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import Response

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from features.api.routes.webui.conversation_attachments.knowledge_responses import (
    knowledge_attachment_summary_response,
)
from features.api.routes.webui.conversation_attachments.route_errors import (
    raise_attachment_route_error,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    get_request_trace_id,
    resolve_api_context,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.knowledge_attachment_task_cancellation import (
    cancel_knowledge_attachment_tasks,
    resolve_knowledge_cancellation_target,
)

__all__ = ("register_knowledge_attachment_delete_routes",)

LOGGER_NAME = "SoAI.features.api.knowledge_delete_routes"
OPERATION_WEBUI_KNOWLEDGE_ATTACHMENT_DELETE_ROUTE = (
    "webui.conversation_attachments.knowledge_delete_route"
)
KNOWLEDGE_ATTACHMENT_DELETE_ROUTE_ERROR_MESSAGE = "Draft knowledge attachment delete route failed."


def register_knowledge_attachment_delete_routes(routers: ApiRouters) -> None:
    @routers.webui.delete(
        "/conversations/{conv_id}/knowledge-attachments/{knowledge_attachment_id}",
    )
    async def remove_draft_knowledge_attachment(
        request: Request,
        conv_id: str,
        knowledge_attachment_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            user_id = current_user["id"]
            target = await resolve_knowledge_cancellation_target(
                request, api_context, conv_id, user_id, knowledge_attachment_id
            )
            summary = await target.repository.remove_draft_knowledge_attachment(
                conv_id=target.resolved_conv_id,
                user_id=user_id,
                knowledge_attachment_id=knowledge_attachment_id,
            )
            task_id = summary.get("task_id")
            processing_state = summary.get("processing_state")
            summary_task_ids = [task_id] if isinstance(task_id, str) else []
            if processing_state == "cancelling":
                await cancel_knowledge_attachment_tasks(
                    api_context.dependencies.task_registry,
                    task_ids=(*target.active_task_ids, *summary_task_ids),
                    reason="Draft knowledge attachment removed.",
                )
            return await knowledge_attachment_summary_response(
                api_context.dependencies.event_bus,
                summary=summary,
            )
        except (ConflictError, ValidationError) as exception:
            raise_attachment_route_error(request, exception)
        except RECOVERABLE_EXCEPTIONS as exception:
            route_logger = get_logger(LOGGER_NAME)
            log_exception(
                route_logger,
                exception,
                message=KNOWLEDGE_ATTACHMENT_DELETE_ROUTE_ERROR_MESSAGE,
                operation=OPERATION_WEBUI_KNOWLEDGE_ATTACHMENT_DELETE_ROUTE,
                trace_id=get_request_trace_id(request),
            )
            raise_attachment_route_error(request, exception, already_logged=True)
