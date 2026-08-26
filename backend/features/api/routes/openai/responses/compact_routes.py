"""SoAI - OpenAI Responses compact endpoint [backend/features/api/routes/openai/responses/compact_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from starlette.responses import Response

from core.openai.openai_current import RESPONSES_COMPACT_FIELDS
from core.openai.token_accounting import count_prompt_occupancy_async
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.timing.epoch import epoch_seconds
from core.validation.strings import coerce_optional_trimmed_str
from features.api.openai.request_payloads import parse_object_body_json_or_form
from features.api.routes.openai.responses.input_tokens_items import (
    build_effective_input_items,
)
from features.api.routes.openai.responses.payload_parsing import (
    parse_optional_responses_input_value_or_response,
    require_responses_model_known_fields,
)
from features.api.routes.openai.responses.token_count_validation import (
    require_complete_responses_input_token_count,
)
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.response_body import create_json_body_response

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("register_routes",)


def _normalize_message_item(item: JSONDict) -> JSONDict:
    copied: JSONDict = dict(item)
    if copied.get("type") != "message":
        return copied
    item_id_value = copied.get("id")
    if not isinstance(item_id_value, str) or not item_id_value.strip():
        copied["id"] = create_prefixed_hex_id("msg")
    role_value = copied.get("role")
    if not isinstance(role_value, str) or not role_value.strip():
        copied["role"] = "unknown"
    content_value = copied.get("content")
    if content_value is None:
        copied["content"] = []
    elif isinstance(content_value, str):
        copied["content"] = [{"type": "input_text", "text": content_value}]
    elif isinstance(content_value, list):
        copied["content"] = list(content_value)
    else:
        copied["content"] = []
    if "status" not in copied:
        copied["status"] = "completed"
    return copied


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_public.post(
        "/responses/compact",
        tags=["OpenAI Responses"],
        dependencies=[openai_api_dependency()],
    )
    async def responses_compact(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        context = request.state.context
        parsed = await parse_object_body_json_or_form(request, trace_id=context.trace_id)
        if isinstance(parsed, Response):
            return parsed
        payload_json: dict[str, JSONValue] = parsed
        model_or_error = require_responses_model_known_fields(
            payload_json,
            allowed_fields=RESPONSES_COMPACT_FIELDS,
            trace_id=context.trace_id,
        )
        if isinstance(model_or_error, Response):
            return model_or_error
        model = model_or_error
        instructions = coerce_optional_trimmed_str(payload_json.get("instructions"))
        previous_response_id = coerce_optional_trimmed_str(payload_json.get("previous_response_id"))
        input_value = parse_optional_responses_input_value_or_response(
            payload_json,
            trace_id=context.trace_id,
        )
        if isinstance(input_value, Response):
            return input_value
        effective_items = await build_effective_input_items(
            api_context,
            request,
            input_value=input_value,
            instructions=None,
            previous_response_id=previous_response_id,
            conversation_id=None,
        )
        if isinstance(effective_items, Response):
            return effective_items
        input_items = list(effective_items)
        compaction_id = create_prefixed_hex_id("cmp")
        response_id = create_prefixed_hex_id("resp")
        output_items: list[JSONDict] = []
        if instructions is not None:
            output_items.append(
                {
                    "id": create_prefixed_hex_id("msg"),
                    "type": "message",
                    "status": "completed",
                    "role": "system",
                    "content": [{"type": "input_text", "text": instructions}],
                },
            )
        encrypted_content = (
            api_context.dependencies.database_openai_responses.encrypt_compaction_content(
                content={
                    "format": "soai.openai.responses.compaction.v1",
                    "model": model,
                    "instructions": instructions,
                    "items": input_items,
                },
            )
        )
        output_items.extend(input_items)
        output_items.append(
            {"id": compaction_id, "type": "compaction", "encrypted_content": encrypted_content},
        )
        token_payload: dict[str, JSONValue] = {"model": model, "input": list(input_items)}
        if instructions is not None:
            token_payload["input"] = [
                {
                    "id": create_prefixed_hex_id("msg"),
                    "type": "message",
                    "role": "system",
                    "content": [{"type": "input_text", "text": instructions}],
                },
                *list(input_items),
            ]
        token_occupancy = await count_prompt_occupancy_async(
            prompt_token_counter=api_context.dependencies.prompt_token_counter,
            request_payload=token_payload,
        )
        input_tokens_value = require_complete_responses_input_token_count(
            request,
            token_occupancy,
        )
        usage: JSONDict = {
            "input_tokens": input_tokens_value,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 0,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": input_tokens_value,
        }
        return create_json_body_response(
            content={
                "id": response_id,
                "object": "response.compaction",
                "created_at": int(epoch_seconds()),
                "output": [_normalize_message_item(item) for item in output_items],
                "usage": usage,
            },
        )
