"""SoAI - Atomic conversation message regeneration routes [backend/features/api/routes/webui/conversation_message_regeneration_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from starlette.responses import JSONResponse, Response

from core.conversations.settings_authority import resolve_conversation_settings_authority
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ConflictError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.conversation_publication import (
    publish_conversation_updated_and_message_saved,
)
from core.logging.trace import get_logger
from core.model_settings.normalization import resolve_execution_model_sequence
from core.types.json import JSONDict
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.api.routes.webui.conversation_lifecycle_admission import (
    require_idle_conversation_stream_lifecycle,
    run_tracked_conversation_admission,
)
from features.api.routes.webui.conversation_message_regeneration_receipts import (
    serialize_conversation_regeneration_attempt,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.content_preview_feedback import parse_content_preview_feedback
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.conversation_execution_settings import (
    resolve_conversation_execution_settings,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import (
    raise_conflict,
    raise_invalid_request,
    raise_not_found,
)
from features.api.runtime.model_openai_capability_validation import (
    require_openai_capability_for_model,
)
from features.api.runtime.preview_contract_feedback import (
    parse_preview_contract_feedback,
)
from features.api.schemas.conversation_regenerations import (
    ConversationMessageRegenerateRequest,
)

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.conversation_message_regeneration_routes"
OPERATION_REGENERATION_PUBLICATION = "webui.conversation.regeneration.publish"


def _build_regeneration_command(payload: ConversationMessageRegenerateRequest) -> JSONDict:
    command: JSONDict = {
        "expected_last_modified_at_ms": payload.expected_last_modified_at_ms,
    }
    if payload.target is not None:
        command["target"] = payload.target.model_dump()
    if payload.retry_input_id is not None:
        command["retry_input_id"] = payload.retry_input_id
    if payload.content_preview_feedback is not None:
        command["content_preview_feedback"] = dict(payload.content_preview_feedback)
    if payload.preview_contract_feedback is not None:
        command["preview_contract_feedback"] = dict(payload.preview_contract_feedback)
    return command


async def _read_regeneration_replay(
    api_context: ApiContext,
    *,
    conv_id: str,
    user_id: int,
    client_id: str,
    client_request_id: str,
    command: JSONDict,
) -> JSONDict | None:
    existing = await api_context.dependencies.database_regenerations.get_attempt(
        conv_id=conv_id,
        user_id=user_id,
        client_id=client_id,
        client_request_id=client_request_id,
    )
    if existing is None:
        return None
    stored_command = existing.get("regeneration_request")
    if not isinstance(stored_command, dict) or stored_command != command:
        raise ConflictError("Conversation regeneration identity command conflict.")
    existing["regeneration_replayed"] = True
    return existing


async def _publish_acceptance(
    api_context: ApiContext,
    *,
    user_id: int,
    conv_id: str,
    attempt: JSONDict,
) -> None:
    revision = attempt.get("regeneration_accepted_revision")
    message_count = attempt.get("message_count")
    if not isinstance(revision, int) or not isinstance(message_count, int):
        raise ValidationError("Conversation regeneration acceptance result is invalid.")
    try:
        await publish_conversation_updated_and_message_saved(
            api_context.dependencies.event_bus,
            user_id=user_id,
            conv_id=conv_id,
            message_count=message_count,
            last_modified_at_ms=revision,
        )
        await publish_current_input_queue_changed(
            api_dependencies=api_context.dependencies,
            user_id=user_id,
            conv_id=conv_id,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Conversation regeneration publication failed after acceptance.",
            operation=OPERATION_REGENERATION_PUBLICATION,
            level="warning",
            details={"user_id": user_id, "conv_id": conv_id},
        )


async def _commit_regeneration_admission(
    api_context: ApiContext,
    *,
    user_id: int,
    conv_id: str,
    payload: ConversationMessageRegenerateRequest,
    command: JSONDict,
    effective_settings: JSONDict,
    settings_authority: JSONDict,
) -> JSONDict:
    registry = api_context.dependencies.chat_stream_registry
    async with registry.lifecycle_lock(user_id=user_id, conv_id=conv_id):
        replay = await _read_regeneration_replay(
            api_context,
            conv_id=conv_id,
            user_id=user_id,
            client_id=payload.client_id,
            client_request_id=payload.client_request_id,
            command=command,
        )
        if replay is not None:
            return replay
        await require_idle_conversation_stream_lifecycle(
            api_context,
            user_id=user_id,
            conv_id=conv_id,
        )
        return await api_context.dependencies.database_regenerations.admit(
            conv_id=conv_id,
            user_id=user_id,
            client_id=payload.client_id,
            client_request_id=payload.client_request_id,
            regeneration_request=command,
            model_settings=effective_settings,
            settings_authority=settings_authority,
        )


async def _require_regeneration_models_available(
    api_context: ApiContext,
    effective_settings: JSONDict,
) -> None:
    for model_name in resolve_execution_model_sequence(effective_settings):
        await require_openai_capability_for_model(
            model_resolution_service=api_context.dependencies.model_resolution_service,
            model_information_service=api_context.dependencies.model_information_service,
            virtual_model_get=(
                api_context.dependencies.model_virtual_model_service.virtual_model_get
            ),
            model_name=model_name,
            capability_key="chat_completions",
            label="Conversation regeneration model",
        )


async def regenerate_conversation_message(
    request: Request,
    conv_id: str,
    payload: ConversationMessageRegenerateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    resolved_conv_id = conversation_context.resolved_conv_id
    command = _build_regeneration_command(payload)
    replay = await _read_regeneration_replay(
        api_context,
        conv_id=resolved_conv_id,
        user_id=current_user["id"],
        client_id=payload.client_id,
        client_request_id=payload.client_request_id,
        command=command,
    )
    if replay is not None:
        return JSONResponse(
            content=serialize_conversation_regeneration_attempt(replay),
            status_code=201,
        )
    try:
        parse_content_preview_feedback(command)
        parse_preview_contract_feedback(command)
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    try:
        effective_settings = await resolve_conversation_execution_settings(
            api_context,
            user_id=current_user["id"],
            conversation_record=conversation_context.record,
        )
        settings_authority = resolve_conversation_settings_authority(
            conversation_context.record,
        ).model_settings
        await _require_regeneration_models_available(api_context, effective_settings)
    except HANDLED_RUNTIME_EXCEPTIONS:
        replay = await _read_regeneration_replay(
            api_context,
            conv_id=resolved_conv_id,
            user_id=current_user["id"],
            client_id=payload.client_id,
            client_request_id=payload.client_request_id,
            command=command,
        )
        if replay is not None:
            return JSONResponse(
                content=serialize_conversation_regeneration_attempt(replay),
                status_code=201,
            )
        raise
    try:
        attempt = await run_tracked_conversation_admission(
            api_context,
            admission=_commit_regeneration_admission(
                api_context,
                user_id=current_user["id"],
                conv_id=resolved_conv_id,
                payload=payload,
                command=command,
                effective_settings=effective_settings,
                settings_authority=settings_authority,
            ),
            task_name=f"conversation-regeneration-admission-{payload.client_request_id}",
            cancellation_note="Conversation regeneration admission resolution failed",
        )
    except ConflictError as exception:
        raise_conflict(request, str(exception))
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    if attempt.get("regeneration_replayed") is not True:
        await _publish_acceptance(
            api_context,
            user_id=current_user["id"],
            conv_id=resolved_conv_id,
            attempt=attempt,
        )
    return JSONResponse(
        content=serialize_conversation_regeneration_attempt(attempt),
        status_code=201,
    )


async def get_conversation_regeneration_status(
    request: Request,
    conv_id: str,
    client_id: str | None = Query(default=None, min_length=1, max_length=128),
    client_request_id: str | None = Query(default=None, min_length=1, max_length=128),
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    if (client_id is None) != (client_request_id is None):
        raise_invalid_request(
            request,
            "Regeneration status requires both client_id and client_request_id.",
        )
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    attempt = await api_context.dependencies.database_regenerations.get_attempt(
        conv_id=conversation_context.resolved_conv_id,
        user_id=current_user["id"],
        client_id=client_id,
        client_request_id=client_request_id,
    )
    if attempt is None:
        raise_not_found(request, "Conversation regeneration attempt was not found.")
    return JSONResponse(content=serialize_conversation_regeneration_attempt(attempt))


def register_endpoints(router: APIRouter) -> None:
    router.post("/conversations/{conv_id}/messages/regenerate", status_code=201)(
        regenerate_conversation_message,
    )
    router.get("/conversations/{conv_id}/messages/regenerate/status")(
        get_conversation_regeneration_status,
    )


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.webui)
