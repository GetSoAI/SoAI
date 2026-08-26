"""SoAI - OpenAI Responses input_tokens input item assembly [backend/features/api/routes/openai/responses/input_tokens_items.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import Response

from core.errors.exceptions import ValidationError
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.types.json_value import (
    coerce_json_dict,
    copy_json_dict_list,
)
from core.validation.record_fields import require_json_object_list
from core.validation.strings import coerce_optional_trimmed_str
from features.api.openai.openai_error_responses import build_openai_error_json_response
from features.api.routes.openai.responses.compaction_expansion import (
    expand_responses_compaction_items,
)
from features.api.routes.openai.responses.endpoint_family_record_loading import (
    fetch_owned_response_record_for_request_or_error,
    load_all_response_input_items,
)
from features.api.routes.openai.responses.endpoint_family_response_shared import (
    create_response_server_error,
)
from features.api.routes.openai.responses.input_items_builder import (
    build_response_input_items,
)
from features.api.routes.openai.responses.payload_parsing import (
    parse_optional_responses_input_value_or_response,
)
from features.api.routes.openai.storage_owner import resolve_responses_storage_owner

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.context import ApiContext

__all__ = (
    "build_effective_input_items",
    "build_effective_input_items_from_payload",
    "coerce_responses_conversation_id",
)


def coerce_responses_conversation_id(value: JSONValue) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    conversation = coerce_json_dict(value)
    if conversation is not None:
        candidate = conversation.get("id")
        return candidate.strip() if isinstance(candidate, str) and candidate.strip() else None
    return None


async def build_effective_input_items_from_payload(
    api_context: ApiContext,
    request: Request,
    *,
    payload_json: dict[str, JSONValue],
) -> tuple[JSONDict, ...] | Response:
    trace_id = request.state.context.trace_id
    input_value = parse_optional_responses_input_value_or_response(
        payload_json,
        trace_id=trace_id,
    )
    if isinstance(input_value, Response):
        return input_value
    return await build_effective_input_items(
        api_context,
        request,
        input_value=input_value,
        instructions=coerce_optional_trimmed_str(payload_json.get("instructions")),
        previous_response_id=coerce_optional_trimmed_str(payload_json.get("previous_response_id")),
        conversation_id=coerce_responses_conversation_id(payload_json.get("conversation")),
    )


async def build_effective_input_items(
    api_context: ApiContext,
    request: Request,
    *,
    input_value: str | list[JSONValue] | None,
    instructions: str | None,
    previous_response_id: str | None,
    conversation_id: str | None,
) -> tuple[JSONDict, ...] | Response:
    trace_id = request.state.context.trace_id
    if previous_response_id is not None and conversation_id is not None:
        return build_openai_error_json_response(
            status_code=400,
            message="previous_response_id cannot be used with conversation.",
            canonical_error_type="invalid_request_error",
            param="conversation",
            code=None,
            trace_id=trace_id,
            headers=None,
        )
    requesting_api_key_id, requesting_user_id = resolve_responses_storage_owner(request)
    items: list[JSONDict] = []
    if conversation_id is not None:
        conversation = (
            await api_context.dependencies.database_openai_conversations.get_conversation(
                conversation_id=conversation_id,
                user_id=requesting_user_id,
                api_key_id=requesting_api_key_id,
            )
        )
        if conversation is None:
            return build_openai_error_json_response(
                status_code=404,
                message="Conversation not found.",
                canonical_error_type="invalid_request_error",
                param="conversation",
                code=None,
                trace_id=trace_id,
                headers=None,
            )
        try:
            after: str | None = None
            while True:
                page, has_more = (
                    await api_context.dependencies.database_openai_conversations.list_items(
                        conversation_id=conversation_id,
                        user_id=requesting_user_id,
                        api_key_id=requesting_api_key_id,
                        limit=100,
                        order="asc",
                        after=after,
                        before=None,
                    )
                )
                items.extend(copy_json_dict_list(page))
                if not has_more:
                    break
                last_entry = coerce_json_dict(page[-1]) if page else None
                last_id = last_entry.get("id") if last_entry is not None else None
                if not isinstance(last_id, str) or not last_id.strip():
                    raise ValidationError("Failed to page conversation items.")
                after = last_id
        except ValidationError:
            return create_response_server_error(
                trace_id=trace_id,
                message="Failed to load conversation items.",
            )
    if previous_response_id is not None:
        stored_record = await fetch_owned_response_record_for_request_or_error(
            request,
            api_context,
            response_id=previous_response_id,
            require_stored=True,
            param_name="previous_response_id",
        )
        if isinstance(stored_record, Response):
            return stored_record
        normalized_previous_response_id, record, _api_key_id, _user_id = stored_record
        response_json_value = record.get("response_json")
        stored = coerce_json_dict(response_json_value)
        if stored is None:
            return create_response_server_error(
                trace_id=trace_id,
                message="Stored response payload is missing.",
            )
        try:
            response_input_items = await load_all_response_input_items(
                api_context.dependencies.database_openai_responses,
                response_id=normalized_previous_response_id,
                user_id=requesting_user_id,
                api_key_id=requesting_api_key_id,
            )
        except ValidationError:
            return create_response_server_error(
                trace_id=trace_id,
                message="Failed to load previous response input items.",
            )
        try:
            output_items = require_json_object_list(
                stored.get("output"),
                label="stored response output",
                build_error=ValidationError,
                invalid_message="Stored response payload is invalid.",
                entry_message="Stored response payload is invalid.",
            )
        except ValidationError:
            return create_response_server_error(
                trace_id=trace_id,
                message="Stored response payload is invalid.",
            )
        items.extend(response_input_items)
        items.extend(output_items)
    if input_value is not None:
        try:
            items.extend(build_response_input_items(input_value))
        except ValidationError as exception:
            return build_openai_error_json_response(
                status_code=400,
                message=str(exception),
                canonical_error_type="invalid_request_error",
                param="input",
                code=None,
                trace_id=trace_id,
                headers=None,
            )
    if instructions is not None:
        items.insert(
            0,
            {
                "id": create_prefixed_hex_id("msg"),
                "type": "message",
                "role": "system",
                "content": [{"type": "input_text", "text": instructions}],
            },
        )
    if not items:
        return build_openai_error_json_response(
            status_code=400,
            message="input must be provided when no previous state is supplied.",
            canonical_error_type="invalid_request_error",
            param="input",
            code=None,
            trace_id=trace_id,
            headers=None,
        )
    try:
        expanded = expand_responses_compaction_items(
            database_openai_responses=api_context.dependencies.database_openai_responses,
            input_value=items,
        )
        return tuple(
            require_json_object_list(
                expanded,
                label="expanded input",
                build_error=ValidationError,
                invalid_message="Invalid compaction item.",
                entry_message="Invalid compaction item.",
            ),
        )
    except ValidationError:
        return build_openai_error_json_response(
            status_code=400,
            message="Invalid compaction item.",
            canonical_error_type="invalid_request_error",
            param="input",
            code=None,
            trace_id=trace_id,
            headers=None,
        )
