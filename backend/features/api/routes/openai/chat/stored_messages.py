"""SoAI - OpenAI stored chat completion messages endpoint [backend/features/api/routes/openai/chat/stored_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.runtime.request_trace_id import get_request_trace_id
from core.types.json import JSONDict, JSONValue
from features.api.openai.api_key_auth import require_openai_api_key_id
from features.api.openai.list_payloads import build_openai_list_response
from features.api.routes.openai.chat.stored_common import (
    build_invalid_after_cursor_response,
    build_stored_chat_completion_unavailable_response,
    fetch_stored_chat_completion_record_or_error,
    parse_stored_list_pagination_params,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

__all__ = ("register_routes",)


def _extract_message_text(content: JSONValue) -> str | None:
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or ""
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") != "text":
            continue
        text_value = part.get("text")
        if isinstance(text_value, str) and text_value:
            parts.append(text_value)
    if not parts:
        return None
    return "".join(parts)


def _extract_content_parts(content: JSONValue) -> list[JSONDict] | None:
    if not isinstance(content, list):
        return None
    parts: list[JSONDict] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text":
            text_value = part.get("text")
            if isinstance(text_value, str):
                parts.append({"type": "text", "text": text_value})
            continue
        if part_type == "image_url":
            image_url_value = part.get("image_url")
            if isinstance(image_url_value, dict):
                url_value = image_url_value.get("url")
                if isinstance(url_value, str) and url_value:
                    image_url_payload: JSONDict = {"url": url_value}
                    detail_value = image_url_value.get("detail")
                    if isinstance(detail_value, str) and detail_value:
                        image_url_payload["detail"] = detail_value
                    image_part: JSONDict = {"type": "image_url", "image_url": image_url_payload}
                    parts.append(image_part)
            continue
    return parts or None


def _paginate_items(
    *,
    item_ids: tuple[str, ...],
    after: str | None,
    limit: int,
    order: str,
) -> tuple[tuple[str, ...], bool]:
    sequence = item_ids if order == "asc" else tuple(reversed(item_ids))
    start = 0
    if after is not None:
        start = sequence.index(after) + 1
    end = start + limit
    sliced = sequence[start:end]
    has_more = end < len(sequence)
    return (tuple(sliced), has_more)


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.get(
        "/chat/completions/{completion_id}/messages",
        tags=["Chat"],
        dependencies=[openai_api_dependency()],
    )
    async def get_chat_completion_messages(
        completion_id: str,
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        trace_id = get_request_trace_id(request)
        api_key_id_or_error = require_openai_api_key_id(request)
        if isinstance(api_key_id_or_error, JSONResponse):
            return api_key_id_or_error
        record_or_response = await fetch_stored_chat_completion_record_or_error(
            api_context.dependencies.database_openai_chat_completions,
            completion_id=completion_id,
            api_key_id=api_key_id_or_error,
            trace_id=trace_id,
        )
        if isinstance(record_or_response, JSONResponse):
            return record_or_response
        record = record_or_response
        request_json = record.get("request_json")
        if not isinstance(request_json, dict):
            return build_stored_chat_completion_unavailable_response(trace_id=trace_id)
        messages_value = request_json.get("messages")
        if not isinstance(messages_value, list):
            messages_value = []
        message_ids: list[str] = []
        message_payloads: dict[str, JSONDict] = {}
        for index, message in enumerate(messages_value):
            if not isinstance(message, dict):
                continue
            msg_id = f"{completion_id}-{index}"
            role_value = message.get("role")
            role = role_value if isinstance(role_value, str) and role_value else "user"
            content_value = message.get("content")
            msg_payload: JSONDict = {
                "id": msg_id,
                "role": role,
                "content": _extract_message_text(content_value),
                "refusal": None,
                "name": message.get("name") if isinstance(message.get("name"), str) else None,
                "content_parts": _extract_content_parts(content_value),
            }
            message_ids.append(msg_id)
            message_payloads[msg_id] = msg_payload
        pagination = parse_stored_list_pagination_params(request)
        if isinstance(pagination, JSONResponse):
            return pagination
        if pagination.after is not None and pagination.after not in message_payloads:
            return build_invalid_after_cursor_response(
                message="after must reference an existing stored chat completion message.",
                trace_id=trace_id,
            )
        selected_ids, has_more = _paginate_items(
            item_ids=tuple(message_ids),
            after=pagination.after,
            limit=pagination.limit,
            order=pagination.order,
        )
        data = [message_payloads[msg_id] for msg_id in selected_ids]
        return build_openai_list_response(data=data, has_more=has_more)
