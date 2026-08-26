"""SoAI - Authenticated chat preset API routes [backend/features/api/routes/webui/chat_preset_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from core.chat_presets.contracts import ChatPresetMutationResult, ChatPresetProjectedRecord
from core.errors.exceptions import PayloadTooLargeError, StateError, ValidationError
from core.types.json import JSONDict
from features.api.routes.webui.chat_preset_diagnostics import (
    ChatPresetIntegrityDiagnostics,
)
from features.api.routes.webui.chat_preset_request_validation import (
    map_chat_preset_validation_error,
    read_chat_preset_payload,
    require_addressed_delete_query,
    require_chat_preset_path_id,
    require_reset_query,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, get_request_trace_id, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_not_found
from features.api.runtime.responses import create_no_content_response
from features.api.schemas.chat_presets import (
    ChatPresetCreateRequest,
    ChatPresetRenameRequest,
    ChatPresetReplaceRequest,
)

__all__ = ("register_routes",)


def _require_sections(raw_payload: JSONDict) -> JSONDict:
    sections = raw_payload.get("sections")
    if not isinstance(sections, dict):
        raise ValidationError("Chat preset sections must be an object.")
    return sections


def _require_mutation_success(request: Request, result: ChatPresetMutationResult) -> None:
    status = result["status"]
    if status == "success":
        return
    if status == "not_found":
        raise_not_found(request, "Chat preset not found.")
    error_messages = {
        "name_conflict": "A chat preset with this name already exists.",
        "revision_conflict": "The chat preset changed before this operation completed.",
        "revision_exhausted": "The chat preset revision cannot be advanced.",
        "limit_reached": "The chat preset library limit has been reached.",
        "corrupt_record": "The chat preset record is corrupt. Reset the preset library.",
    }
    error_types = {
        "name_conflict": "chat_preset_name_conflict",
        "revision_conflict": "chat_preset_revision_conflict",
        "revision_exhausted": "chat_preset_revision_exhausted",
        "limit_reached": "chat_preset_limit_reached",
        "corrupt_record": "chat_preset_corrupt_record",
    }
    raise_conflict(request, error_messages[status], error_type=error_types[status])


def _return_mutation(
    request: Request, result: ChatPresetMutationResult
) -> ChatPresetProjectedRecord:
    _require_mutation_success(request, result)
    preset = result["preset"]
    if preset is None:
        raise StateError("Successful chat preset record mutation has no record.")
    return preset


def _raise_validation(request: Request, exception: Exception) -> NoReturn:
    map_chat_preset_validation_error(request, exception)
    raise StateError("Chat preset validation mapping returned unexpectedly.")


def register_routes(routers: ApiRouters) -> None:
    integrity_diagnostics = ChatPresetIntegrityDiagnostics()

    @routers.webui.get("/chat/presets")
    async def list_chat_presets(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        result = await api_context.dependencies.database_chat_presets.list_chat_presets(
            current_user["id"]
        )
        integrity_diagnostics.log(
            user_id=current_user["id"],
            invalid_count=result["structurally_invalid_count"],
            trace_id=get_request_trace_id(request),
        )
        return JSONResponse(content=result)

    @routers.webui.post("/chat/presets", status_code=201)
    async def create_chat_preset(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        payload, raw_payload = await read_chat_preset_payload(request, ChatPresetCreateRequest)
        try:
            result = await api_context.dependencies.database_chat_presets.create_chat_preset(
                user_id=current_user["id"],
                name=payload.name,
                sections=_require_sections(raw_payload),
            )
        except (PayloadTooLargeError, ValidationError) as exception:
            _raise_validation(request, exception)
        preset = _return_mutation(request, result)
        log_audit_event(request, "CREATE_CHAT_PRESET", "chat_preset_library")
        return JSONResponse(content=preset, status_code=201)

    @routers.webui.patch("/chat/presets/{preset_id}")
    async def rename_chat_preset(
        request: Request,
        preset_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        resolved_id = require_chat_preset_path_id(request, preset_id)
        payload, _raw_payload = await read_chat_preset_payload(request, ChatPresetRenameRequest)
        try:
            result = await api_context.dependencies.database_chat_presets.rename_chat_preset(
                user_id=current_user["id"],
                preset_id=resolved_id,
                expected_revision=payload.expected_revision,
                name=payload.name,
            )
        except ValidationError as exception:
            _raise_validation(request, exception)
        preset = _return_mutation(request, result)
        log_audit_event(request, "RENAME_CHAT_PRESET", resolved_id)
        return JSONResponse(content=preset)

    @routers.webui.put("/chat/presets/{preset_id}")
    async def replace_chat_preset(
        request: Request,
        preset_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        resolved_id = require_chat_preset_path_id(request, preset_id)
        payload, raw_payload = await read_chat_preset_payload(request, ChatPresetReplaceRequest)
        try:
            result = await api_context.dependencies.database_chat_presets.replace_chat_preset(
                user_id=current_user["id"],
                preset_id=resolved_id,
                expected_revision=payload.expected_revision,
                name=payload.name,
                sections=_require_sections(raw_payload),
            )
        except (PayloadTooLargeError, ValidationError) as exception:
            _raise_validation(request, exception)
        preset = _return_mutation(request, result)
        log_audit_event(request, "REPLACE_CHAT_PRESET", resolved_id)
        return JSONResponse(content=preset)

    @routers.webui.delete("/chat/presets/{preset_id}", status_code=204)
    async def delete_chat_preset(
        request: Request,
        preset_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        resolved_id = require_chat_preset_path_id(request, preset_id)
        expected_revision = require_addressed_delete_query(request)
        result = await api_context.dependencies.database_chat_presets.delete_chat_preset(
            user_id=current_user["id"],
            preset_id=resolved_id,
            expected_revision=expected_revision,
        )
        _require_mutation_success(request, result)
        log_audit_event(request, "DELETE_CHAT_PRESET", resolved_id)
        return create_no_content_response()

    @routers.webui.delete("/chat/presets")
    async def reset_chat_presets(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        require_reset_query(request)
        deleted = await api_context.dependencies.database_chat_presets.reset_chat_presets(
            current_user["id"]
        )
        log_audit_event(request, "RESET_CHAT_PRESETS", "chat_preset_library", {"deleted": deleted})
        return JSONResponse(content={"deleted": deleted})
