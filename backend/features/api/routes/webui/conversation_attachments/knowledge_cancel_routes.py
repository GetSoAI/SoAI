"""SoAI - WebUI knowledge attachment cancellation route [backend/features/api/routes/webui/conversation_attachments/knowledge_cancel_routes.py]"""
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

__all__ = ("register_knowledge_attachment_cancel_route",)

LOGGER_NAME = "SoAI.features.api.knowledge_cancel_routes"
OPERATION = "webui.conversation_attachments.knowledge_cancel_route"
ERROR_MESSAGE = "Conversation knowledge attachment cancellation route failed."
CANCELLATION_REASON = "Knowledge attachment cancelled."


def register_knowledge_attachment_cancel_route(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/knowledge-attachments/{knowledge_attachment_id}/cancel",
    )
    async def cancel_knowledge_attachment(
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
            summary = await target.repository.cancel_knowledge_attachment(
                conv_id=target.resolved_conv_id,
                user_id=user_id,
                knowledge_attachment_id=knowledge_attachment_id,
            )
            task_id = summary.get("task_id")
            summary_task_ids = [task_id] if isinstance(task_id, str) else []
            if summary.get("processing_state") == "cancelling":
                await cancel_knowledge_attachment_tasks(
                    api_context.dependencies.task_registry,
                    task_ids=(*target.active_task_ids, *summary_task_ids),
                    reason=CANCELLATION_REASON,
                )
                if summary_task_ids and not target.active_task_ids:
                    finalized = await target.repository.finalize_knowledge_attachment_task(
                        task_id=summary_task_ids[0],
                        processing_state="cancelled",
                        terminal_item_status="cancelled",
                        error_message=CANCELLATION_REASON,
                    )
                    if finalized is not None:
                        summary = finalized
            return await knowledge_attachment_summary_response(
                api_context.dependencies.event_bus,
                summary=summary,
            )
        except (ConflictError, ValidationError) as exception:
            raise_attachment_route_error(request, exception)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message=ERROR_MESSAGE,
                operation=OPERATION,
                trace_id=get_request_trace_id(request),
            )
            raise_attachment_route_error(request, exception, already_logged=True)
