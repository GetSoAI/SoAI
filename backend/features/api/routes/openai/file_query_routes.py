"""SoAI - OpenAI file query and content routes [backend/features/api/routes/openai/file_query_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import Response

from core.events.types_files import (
    FileContentQuery,
    FileDeleteCommand,
    FileRetrieveQuery,
)
from core.files.export import build_content_disposition_attachment
from core.openai.file_list_limits import (
    OPENAI_FILE_LIST_DEFAULT_LIMIT,
    OPENAI_FILE_LIST_MAX_LIMIT,
)
from core.openai.file_objects import format_openai_file_object_from_catalog_record
from core.runtime.request_trace_id import get_request_trace_id
from core.validation.strings import coerce_optional_trimmed_str
from features.api.openai.list_payloads import build_openai_list_response
from features.api.openai.openai_error_responses import (
    build_openai_invalid_request_json_response,
)
from features.api.openai.query_params import parse_openai_list_query_params
from features.api.routes.openai.storage_owner import resolve_file_storage_owner
from features.api.runtime.access_dependencies import openai_api_dependency
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_not_found
from features.api.streaming.openai_stream_binary_request_handler import (
    handle_streaming_binary_request,
)

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.openai_files.get("", dependencies=[openai_api_dependency()])
    async def list_files(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        api_key_id, user_id = resolve_file_storage_owner(request)
        pagination = parse_openai_list_query_params(
            request,
            default_order="desc",
            default_limit=OPENAI_FILE_LIST_DEFAULT_LIMIT,
            strict_order=True,
            strict_positive_limit=True,
            max_limit=OPENAI_FILE_LIST_MAX_LIMIT,
        )
        if isinstance(pagination, Response):
            return pagination
        purpose = coerce_optional_trimmed_str(request.query_params.get("purpose"))
        files = await api_context.dependencies.database_files.list_files(
            enforce_owner=True,
            user_id=user_id,
            api_key_id=api_key_id,
            purpose=purpose,
            after=pagination.after,
            limit=pagination.limit,
            order=pagination.order,
        )
        if files.invalid_after:
            return _build_invalid_after_cursor_response(request)
        data = [
            format_openai_file_object_from_catalog_record(file_entry)
            for file_entry in files.records
        ]
        return build_openai_list_response(
            data=data,
            has_more=files.has_more,
        )

    @routers.openai_files.get("/{file_id}", dependencies=[openai_api_dependency()])
    async def retrieve_file(
        request: Request,
        file_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        api_key_id, user_id = resolve_file_storage_owner(request)
        return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
            request,
            FileRetrieveQuery,
            "final",
            "RETRIEVE_FILE_INFO",
            file_id,
            command_fields={
                "file_id": file_id,
                "user_id": user_id,
                "api_key_id": api_key_id,
            },
        )

    @routers.openai_files.delete("/{file_id}", dependencies=[openai_api_dependency()])
    async def delete_file(
        request: Request,
        file_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        api_key_id, user_id = resolve_file_storage_owner(request)
        return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
            request,
            FileDeleteCommand,
            "final",
            "DELETE_FILE",
            file_id,
            command_fields={
                "file_id": file_id,
                "user_id": user_id,
                "api_key_id": api_key_id,
            },
        )

    @routers.openai_files.get("/{file_id}/content", dependencies=[openai_api_dependency()])
    async def retrieve_file_content(
        request: Request,
        file_id: str,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        api_key_id, user_id = resolve_file_storage_owner(request)
        file_info = await api_context.dependencies.database_files.get_file_info(
            file_id,
            enforce_owner=True,
            user_id=user_id,
            api_key_id=api_key_id,
        )
        if not file_info:
            raise_not_found(request, f"File with ID '{file_id}' not found.")
        filename_value = file_info.get("filename")
        filename = filename_value if isinstance(filename_value, str) else "file"
        response = await handle_streaming_binary_request(
            request,
            {"file_id": file_id, "model": f"file:{file_id}"},
            FileContentQuery,
            "application/octet-stream",
            api_context=api_context,
            base_capabilities=("files",),
            request_user_id=user_id,
            request_api_key_id=api_key_id,
        )
        if response.status_code < 400:
            response.headers.update(
                {"Content-Disposition": build_content_disposition_attachment(filename)},
            )
        return response


def _build_invalid_after_cursor_response(request: Request) -> Response:
    return build_openai_invalid_request_json_response(
        message="after must reference an existing file in the current list.",
        param="after",
        trace_id=get_request_trace_id(request),
        status_code=400,
    )
