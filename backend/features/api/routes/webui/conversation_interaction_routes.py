"""SoAI - Unified WebUI conversation interaction routes [backend/features/api/routes/webui/conversation_interaction_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.elicitation_interactions import (
    extract_notification_id,
    require_supported_interaction_type,
)
from core.errors.exceptions import ValidationError
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request, raise_not_found
from features.api.runtime.request_payloads import read_json_object_payload_or_raise
from features.chat.interaction_service import (
    ConversationInteractionResolutionDependencies,
    get_pending_interaction,
    resolve_interaction,
)
from features.chat.interaction_tasks import (
    require_conversation_access_and_list_pending_conversation_interactions,
    require_conversation_access_and_pending_conversation_interaction_task,
)

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/conversations/{conv_id}/interactions/focus")
    async def resolve_conversation_interaction_focus(
        request: Request,
        conv_id: str,
        interaction_focus: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        focus_nonce = interaction_focus.strip()
        if not focus_nonce or len(focus_nonce) > 128:
            raise_invalid_request(request, "interaction_focus is invalid.")
        await require_conversation_access(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        focus = await api_context.dependencies.database_messaging_ingress.resolve_interaction_focus(
            user_id=current_user["id"],
            conv_id=conv_id,
            focus_nonce=focus_nonce,
        )
        if focus is None:
            raise_not_found(request, "Interaction focus is unavailable.")
        return JSONResponse(content=focus)

    @routers.webui.get("/conversations/{conv_id}/interactions/pending")
    async def list_pending_conversation_interactions(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        interactions = await require_conversation_access_and_list_pending_conversation_interactions(
            request,
            api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        return JSONResponse(content={"conv_id": conv_id, "interactions": interactions})

    @routers.webui.get("/conversations/{conv_id}/interactions/{interaction_type}/pending")
    async def get_pending_conversation_interaction(
        request: Request,
        conv_id: str,
        interaction_type: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            normalized_type = require_supported_interaction_type(interaction_type)
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        envelope = await get_pending_interaction(
            request,
            api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
            interaction_type=normalized_type,
        )
        return JSONResponse(
            content={"conv_id": envelope.conv_id, "interaction": envelope.interaction},
        )

    @routers.webui.post(
        "/conversations/{conv_id}/interactions/{interaction_type}/{task_id}/resolve",
    )
    async def resolve_conversation_interaction(
        request: Request,
        conv_id: str,
        interaction_type: str,
        task_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            normalized_type = require_supported_interaction_type(interaction_type)
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        body = await read_json_object_payload_or_raise(
            request,
            invalid_json_message="Request body must be valid JSON.",
            invalid_object_message="Request body must be a JSON object.",
        )
        await require_conversation_access(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        payload = await resolve_interaction(
            ConversationInteractionResolutionDependencies(
                task_registry=api_context.dependencies.task_registry,
                database_notifications=api_context.dependencies.database_notifications,
            ),
            conv_id=conv_id,
            task_id=task_id,
            user_id=current_user["id"],
            interaction_type=normalized_type,
            payload=body,
        )
        return JSONResponse(content=payload)

    @routers.webui.post("/conversations/{conv_id}/attention/rendered", status_code=204)
    async def acknowledge_conversation_attention_rendered(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        body = await read_json_object_payload_or_raise(
            request,
            invalid_json_message="Request body must be valid JSON.",
            invalid_object_message="Request body must be a JSON object.",
        )
        task_id = str(body.get("task_id") or "").strip()
        notification_id = str(body.get("notification_id") or "").strip()
        if not task_id or not notification_id:
            raise_invalid_request(request, "task_id and notification_id are required.")
        try:
            normalized_type = require_supported_interaction_type(
                str(body.get("interaction_type") or ""),
            )
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        _task_registry, task = (
            await require_conversation_access_and_pending_conversation_interaction_task(
                request,
                api_context,
                conv_id=conv_id,
                user_id=current_user["id"],
                task_id=task_id,
                interaction_type=normalized_type,
            )
        )
        expected_notification_id = extract_notification_id(task.metadata)
        if expected_notification_id != notification_id:
            raise_invalid_request(request, "notification_id does not match the interaction task.")
        api_context.dependencies.conversation_attention.acknowledge_rendered(
            user_id=current_user["id"],
            conversation_id=conv_id,
            interaction_type=normalized_type,
            task_id=task_id,
            notification_id=notification_id,
        )
        await api_context.dependencies.database_notifications.mark_notifications_read(
            current_user["id"],
            notification_ids=[notification_id],
        )
        return Response(status_code=204)
