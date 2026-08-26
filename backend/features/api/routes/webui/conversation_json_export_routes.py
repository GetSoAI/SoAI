"""SoAI - Conversation JSON export WebUI routes [backend/features/api/routes/webui/conversation_json_export_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from fastapi.responses import StreamingResponse
from starlette.responses import Response

from core.files.export import build_content_disposition_attachment
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict, JSONValue
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_not_found
from features.api.schemas.conversations import ConversationJsonExportRequest

__all__ = ("register_routes",)


def _json_bytes(value: JSONValue) -> bytes:
    return serialize_json_compact_stable_strict(value).encode("utf-8")


async def _iter_json_export_bytes(
    *,
    api_context: ApiContext,
    user_id: int,
    conversation: JSONDict,
    payload: ConversationJsonExportRequest,
) -> AsyncIterator[bytes]:
    model_settings = conversation.get("model_settings")
    model_value: JSONValue = payload.active_model
    if model_value is None and isinstance(model_settings, dict):
        settings_model = model_settings.get("model")
        model_value = settings_model if isinstance(settings_model, str) else None
    yield b"{"
    fields: list[tuple[str, JSONValue]] = [
        ("title", conversation.get("title")),
        ("id", conversation.get("id")),
        ("created_at", conversation.get("created_at_ms")),
        ("updated_at", conversation.get("last_modified_at_ms")),
        ("model", model_value),
        ("parameters", payload.parameters),
    ]
    for key, value in fields:
        yield _json_bytes(key)
        yield b":"
        yield _json_bytes(value)
        yield b","
    yield b'"messages":['
    first = True
    async for (
        message
    ) in api_context.dependencies.database_messages.iter_conversation_export_messages(
        str(conversation["id"]),
        user_id,
    ):
        if first:
            first = False
        else:
            yield b","
        yield _json_bytes(message)
    yield b"]}"


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post("/conversations/{conv_id}/export/json")
    async def export_conversation_json(
        request: Request,
        conv_id: str,
        payload: ConversationJsonExportRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        conversation = await api_context.dependencies.database_conversations.get_conversation(
            conv_id,
            current_user["id"],
        )
        if conversation is None:
            raise_not_found(
                request,
                "Conversation not found or you do not have permission to access it.",
            )
        filename = f"chat-{conversation['id']}.json"
        return StreamingResponse(
            _iter_json_export_bytes(
                api_context=api_context,
                user_id=current_user["id"],
                conversation=conversation,
                payload=payload,
            ),
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": build_content_disposition_attachment(filename),
                "Cache-Control": "no-store",
            },
        )
