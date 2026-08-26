"""SoAI - WebUI linked knowledge attachment routes [backend/features/api/routes/webui/conversation_attachments/knowledge_link_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.attachments.linked_knowledge_reservations import (
    estimate_linked_knowledge_reservation_bytes,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.types.json import is_json_dict, is_json_list
from features.api.routes.webui.conversation_attachments.events import (
    publish_knowledge_attachment_changed,
)
from features.api.routes.webui.conversation_attachments.knowledge_contracts import (
    KnowledgeAttachmentItemPreviewRequest,
    KnowledgeAttachmentUseRequest,
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
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_knowledge_link_routes",)

LOGGER_NAME = "SoAI.features.api.knowledge_link_routes"
OPERATION_LINKED_KNOWLEDGE_USE = "webui.linked_knowledge.use"
OPERATION_WEBUI_LINKED_KNOWLEDGE_ROUTE = "webui.conversation_attachments.linked_knowledge_route"
LINKED_KNOWLEDGE_ROUTE_ERROR_MESSAGE = "Conversation linked knowledge route failed."


def _configured_use_max_items(api_context: ApiContext) -> int:
    configured = api_context.dependencies.config.get_int(
        "SERVER.WEBUI.KNOWLEDGE_LINKS.USE_MAX_ITEMS",
    )
    if configured <= 0:
        raise ValidationError("Linked knowledge item limit is invalid.")
    return configured


def _item_ids(body: KnowledgeAttachmentUseRequest, *, max_items: int) -> tuple[int, ...]:
    if not body.selections:
        raise ValidationError("Linked knowledge selection is required.")
    if len(body.selections) > max_items:
        raise ValidationError("Linked knowledge selection exceeds the configured limit.")
    item_ids = tuple(sorted(selection.item_id for selection in body.selections))
    if len(set(item_ids)) != len(item_ids):
        raise ValidationError("Linked knowledge item selections must be unique.")
    return item_ids


def _selected_items(payload: JSONDict) -> list[JSONDict]:
    raw_items = payload.get("selected_items")
    if not is_json_list(raw_items):
        raise ValidationError("Linked knowledge selection payload is invalid.")
    selected_items: list[JSONDict] = []
    for item in raw_items:
        if not is_json_dict(item):
            raise ValidationError("Linked knowledge selection item is invalid.")
        selected_items.append(item)
    return selected_items


def _existing_summary(payload: JSONDict) -> JSONDict | None:
    raw_summary = payload.get("existing_summary")
    if raw_summary is None:
        return None
    if not is_json_dict(raw_summary):
        raise ValidationError("Linked knowledge idempotency payload is invalid.")
    return raw_summary


def _used_summary(payload: JSONDict) -> JSONDict:
    summary = payload.get("summary")
    if not is_json_dict(summary):
        raise ValidationError("Linked knowledge write result summary is invalid.")
    return summary


def _use_result_is_idempotent(payload: JSONDict) -> bool:
    idempotent = payload.get("idempotent")
    if not isinstance(idempotent, bool):
        raise ValidationError("Linked knowledge write result idempotency is invalid.")
    return idempotent


def _validate_document_id_hints(
    *,
    body: KnowledgeAttachmentUseRequest,
    selected_items: list[JSONDict],
) -> None:
    document_ids_by_item_id: dict[int, str] = {}
    for item in selected_items:
        source_item_id = item.get("source_item_id")
        source_document_id = item.get("source_document_id")
        if not isinstance(source_item_id, int) or not isinstance(source_document_id, str):
            raise ValidationError("Linked knowledge canonical selection is invalid.")
        document_ids_by_item_id[source_item_id] = source_document_id
    for selection in body.selections:
        if selection.document_id is None:
            continue
        if document_ids_by_item_id.get(selection.item_id) != selection.document_id:
            raise ValidationError("Linked knowledge document id does not match the selected item.")


async def _resolve_use_context(
    *,
    request: Request,
    api_context: ApiContext,
    target_conv_id: str,
    source_conv_id: str,
    user_id: int,
) -> tuple[str, str]:
    target_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=target_conv_id,
        user_id=user_id,
    )
    source_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=source_conv_id,
        user_id=user_id,
    )
    return target_context.resolved_conv_id, source_context.resolved_conv_id


def register_knowledge_link_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/knowledge-attachments/{knowledge_attachment_id}/items/{item_id}/preview",
    )
    async def preview_knowledge_attachment_item(
        request: Request,
        conv_id: str,
        knowledge_attachment_id: str,
        item_id: int,
        body: KnowledgeAttachmentItemPreviewRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            conversation_context = await require_conversation_access_context(
                request,
                api_context=api_context,
                conv_id=conv_id,
                user_id=current_user["id"],
            )
            preview = await api_context.dependencies.database_conversation_linked_knowledge.preview_linked_knowledge_item(
                source_conv_id=conversation_context.resolved_conv_id,
                source_user_id=current_user["id"],
                source_knowledge_attachment_id=knowledge_attachment_id,
                item_id=item_id,
                document_id=body.document_id,
            )
            return JSONResponse(content=preview)
        except (ConflictError, ValidationError) as exception:
            raise_attachment_route_error(request, exception)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message=LINKED_KNOWLEDGE_ROUTE_ERROR_MESSAGE,
                operation=OPERATION_WEBUI_LINKED_KNOWLEDGE_ROUTE,
                trace_id=get_request_trace_id(request),
            )
            raise_attachment_route_error(request, exception, already_logged=True)

    @routers.webui.post("/conversations/{target_conv_id}/knowledge-attachments/use")
    async def use_knowledge_attachment_items(
        request: Request,
        target_conv_id: str,
        body: KnowledgeAttachmentUseRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            item_ids = _item_ids(body, max_items=_configured_use_max_items(api_context))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        try:
            resolved_target_conv_id, resolved_source_conv_id = await _resolve_use_context(
                request=request,
                api_context=api_context,
                target_conv_id=target_conv_id,
                source_conv_id=body.source_conv_id,
                user_id=current_user["id"],
            )
            prepared = await api_context.dependencies.database_conversation_linked_knowledge.prepare_linked_knowledge_use(
                target_conv_id=resolved_target_conv_id,
                target_user_id=current_user["id"],
                source_conv_id=resolved_source_conv_id,
                source_user_id=current_user["id"],
                source_knowledge_attachment_id=body.source_knowledge_attachment_id,
                item_ids=item_ids,
                client_batch_id=body.client_batch_id,
            )
            selected_items = _selected_items(prepared)
            _validate_document_id_hints(body=body, selected_items=selected_items)
            existing_summary = _existing_summary(prepared)
            if existing_summary is not None:
                return JSONResponse(content={"summary": existing_summary, "idempotent": True})
            reservation_bytes = estimate_linked_knowledge_reservation_bytes(
                target_conv_id=resolved_target_conv_id,
                target_user_id=current_user["id"],
                source_conv_id=resolved_source_conv_id,
                source_knowledge_attachment_id=body.source_knowledge_attachment_id,
                client_batch_id=body.client_batch_id,
                selected_items=selected_items,
            )
            details: JSONDict = {
                "target_conv_id": resolved_target_conv_id,
                "source_conv_id": resolved_source_conv_id,
                "selected_item_count": len(selected_items),
            }
            with api_context.dependencies.storage_manager.reserve_disk_space_for_install_volume(
                required_bytes=reservation_bytes,
                operation=OPERATION_LINKED_KNOWLEDGE_USE,
                details=details,
            ) as reservation:
                used = await api_context.dependencies.database_conversation_linked_knowledge.use_linked_knowledge_items(
                    target_conv_id=resolved_target_conv_id,
                    target_user_id=current_user["id"],
                    source_conv_id=resolved_source_conv_id,
                    source_user_id=current_user["id"],
                    source_knowledge_attachment_id=body.source_knowledge_attachment_id,
                    item_ids=item_ids,
                    client_batch_id=body.client_batch_id,
                    reservation=reservation,
                    reservation_bytes=reservation_bytes,
                )
            summary = _used_summary(used)
            idempotent = _use_result_is_idempotent(used)
            if not idempotent:
                await publish_knowledge_attachment_changed(
                    api_context.dependencies.event_bus,
                    summary=summary,
                )
            return JSONResponse(content={"summary": summary, "idempotent": idempotent})
        except (ConflictError, ValidationError) as exception:
            raise_attachment_route_error(request, exception)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message=LINKED_KNOWLEDGE_ROUTE_ERROR_MESSAGE,
                operation=OPERATION_WEBUI_LINKED_KNOWLEDGE_ROUTE,
                trace_id=get_request_trace_id(request),
            )
            raise_attachment_route_error(request, exception, already_logged=True)
