"""SoAI - Shared OpenAI Responses record-loading helpers [backend/features/api/routes/openai/responses/endpoint_family_record_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from starlette.responses import Response

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict
from core.validation.record_fields import require_json_object_list
from features.api.openai.openai_error_responses import build_openai_error_json_response
from features.api.routes.openai.responses.endpoint_family_response_shared import (
    create_response_not_found_error,
    create_response_not_stored_error,
    normalize_response_id_or_error,
    response_record_flag_enabled,
)
from features.api.routes.openai.storage_owner import resolve_responses_storage_owner

if TYPE_CHECKING:
    from core.openai.protocols_database_responses import DatabaseOpenAIResponsesProtocol
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.context import ApiContext

__all__ = (
    "extract_stored_response_json_or_error",
    "fetch_owned_response_input_items_or_error",
    "fetch_owned_response_record_for_request_or_error",
    "fetch_response_record_or_error",
    "load_all_response_input_items",
)


def extract_stored_response_json_or_error(
    record: JSONDict,
    *,
    trace_id: str | None,
) -> JSONDict | Response:
    response_json_value = record.get("response_json")
    response_json = coerce_json_dict(response_json_value)
    if response_json is None:
        return build_openai_error_json_response(
            status_code=502,
            message="Stored response payload is missing.",
            canonical_error_type="server_error",
            param=None,
            code=None,
            trace_id=trace_id,
            headers=None,
        )
    return response_json


async def fetch_response_record_or_error(
    database_openai_responses: DatabaseOpenAIResponsesProtocol,
    *,
    response_id: str,
    trace_id: str,
    user_id: int | None,
    api_key_id: str | None,
    require_stored: bool,
    param_name: str = "response_id",
) -> dict[str, JSONValue] | Response:
    record = await database_openai_responses.get_response_record(
        response_id=response_id,
        user_id=user_id,
        api_key_id=api_key_id,
    )
    if record is None:
        return create_response_not_found_error(trace_id=trace_id, param_name=param_name)
    if require_stored and not response_record_flag_enabled(record, "store"):
        return create_response_not_stored_error(trace_id=trace_id, param_name=param_name)
    return record


async def fetch_owned_response_record_for_request_or_error(
    request: Request,
    api_context: ApiContext,
    *,
    response_id: str,
    require_stored: bool,
    param_name: str = "response_id",
) -> tuple[str, dict[str, JSONValue], str | None, int | None] | Response:
    trace_id = request.state.context.trace_id
    normalized_response_id, error_response = normalize_response_id_or_error(
        response_id,
        trace_id=trace_id,
        param_name=param_name,
    )
    if error_response is not None:
        return error_response
    requesting_api_key_id, requesting_user_id = resolve_responses_storage_owner(request)
    record_or_error = await fetch_response_record_or_error(
        api_context.dependencies.database_openai_responses,
        response_id=normalized_response_id,
        trace_id=trace_id,
        user_id=requesting_user_id,
        api_key_id=requesting_api_key_id,
        require_stored=require_stored,
        param_name=param_name,
    )
    if isinstance(record_or_error, Response):
        return record_or_error
    return (normalized_response_id, record_or_error, requesting_api_key_id, requesting_user_id)


async def fetch_owned_response_input_items_or_error(
    request: Request,
    api_context: ApiContext,
    *,
    response_id: str,
    limit: int,
    order: str,
    after: str | None,
    before: str | None,
) -> dict[str, JSONValue] | Response:
    trace_id = request.state.context.trace_id
    owned_record = await fetch_owned_response_record_for_request_or_error(
        request,
        api_context,
        response_id=response_id,
        require_stored=False,
    )
    if isinstance(owned_record, Response):
        return owned_record
    normalized_response_id, _record, requesting_api_key_id, requesting_user_id = owned_record
    input_items_payload: dict[str, JSONValue] | None = None
    error_response: Response | None = None
    try:
        input_items_payload = (
            await api_context.dependencies.database_openai_responses.list_input_items(
                response_id=normalized_response_id,
                limit=limit,
                order=order,
                after=after,
                before=before,
                user_id=requesting_user_id,
                api_key_id=requesting_api_key_id,
            )
        )
    except ValidationError as exception:
        error_response = build_openai_error_json_response(
            status_code=400,
            message=str(exception),
            canonical_error_type="invalid_request_error",
            param=None,
            code=None,
            trace_id=trace_id,
            headers=None,
        )
    if error_response is not None:
        return error_response
    if input_items_payload is None:
        raise ValidationError("Failed to load response input items.")
    return input_items_payload


async def load_all_response_input_items(
    database_openai_responses: DatabaseOpenAIResponsesProtocol,
    *,
    response_id: str,
    user_id: int | None,
    api_key_id: str | None,
) -> tuple[JSONDict, ...]:
    items: list[JSONDict] = []
    after: str | None = None
    while True:
        payload = await database_openai_responses.list_input_items(
            response_id=response_id,
            limit=100,
            order="asc",
            after=after,
            before=None,
            user_id=user_id,
            api_key_id=api_key_id,
        )
        items.extend(
            require_json_object_list(
                payload.get("data"),
                label="response input items",
                build_error=ValidationError,
                invalid_message="Failed to load response input items.",
                entry_message="Failed to load response input items.",
            ),
        )
        if not bool(payload.get("has_more")):
            return tuple(items)
        last_id = payload.get("last_id")
        if not isinstance(last_id, str) or not last_id.strip():
            raise ValidationError("Failed to page response input items.")
        after = last_id
