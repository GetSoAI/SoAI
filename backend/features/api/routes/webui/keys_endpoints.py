"""SoAI - OpenAI API key management endpoints [backend/features/api/routes/webui/keys_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse

from core.auth.api_keys import (
    create_openai_api_key,
    list_openai_api_keys,
    revoke_openai_api_key,
    rotate_openai_api_key,
)
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from features.api.routes.webui.key_quota_status_listing import list_quota_status_payload
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.api_key_serialization import serialize_api_key_entry
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import (
    raise_not_found,
    raise_server_error,
    raise_service_unavailable,
)
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.webui_records import webui_fetch_or_404
from features.api.schemas.api_keys import (
    OpenAIAPIKeyCreatePayload,
    OpenAIAPIKeyQuotaUpdatePayload,
)

__all__ = (
    "handle_create_openai_api_key",
    "handle_delete_all_openai_api_keys",
    "handle_delete_openai_api_key",
    "handle_get_openai_api_key_quota",
    "handle_list_openai_api_key_quota_status",
    "handle_list_openai_api_keys",
    "handle_revoke_openai_api_key",
    "handle_rotate_openai_api_key",
    "handle_update_openai_api_key_quota",
    "register_endpoints",
    "register_routes",
)


async def handle_list_openai_api_keys(
    _request: Request,
    include_revoked: bool = Query(False),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    records = await list_openai_api_keys(
        api_context.dependencies.webui_manager.database_api_keys,
        include_revoked=include_revoked,
    )
    return JSONResponse(content={"keys": [serialize_api_key_entry(record) for record in records]})


async def handle_create_openai_api_key(
    request: Request,
    payload: OpenAIAPIKeyCreatePayload,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    webui_manager = api_context.dependencies.webui_manager
    primary_signing_secret = api_context.dependencies.auth_config.primary_signing_secret
    if primary_signing_secret is None:
        raise_service_unavailable(request, "Authentication secret key is not configured.")
    created = await create_openai_api_key(
        webui_manager.database_api_keys,
        label=payload.label,
        scopes=payload.scopes,
        created_by=current_user["id"],
        expires_in_days=payload.expires_in_days,
        expires_at_ms=payload.expires_at_ms,
        rotation_reminder_in_days=payload.rotation_reminder_in_days,
        default_ttl_days=webui_manager.key_default_ttl_days,
        default_rotation_days=webui_manager.key_default_rotation_days,
        secret_key=primary_signing_secret,
    )
    token_value = created.pop("key")
    metadata = serialize_api_key_entry(created)
    key_id_value = metadata.get("key_id")
    if not isinstance(key_id_value, str) or not key_id_value:
        raise_server_error(request, "Created API key is missing a key_id.")
    log_audit_event(
        request,
        "CREATE_OPENAI_API_KEY",
        key_id_value,
        {"label": metadata.get("label"), "scopes": metadata.get("scopes")},
    )
    return JSONResponse(
        content={"key": token_value, "metadata": metadata},
        status_code=status.HTTP_201_CREATED,
    )


async def handle_revoke_openai_api_key(
    request: Request,
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    record = await revoke_openai_api_key(
        api_context.dependencies.webui_manager.database_api_keys,
        key_id,
        current_user["id"],
    )
    if not record:
        raise_not_found(request, "API key not found.")
    metadata = serialize_api_key_entry(record)
    log_audit_event(
        request,
        "REVOKE_OPENAI_API_KEY",
        key_id,
        {"revoked_by": current_user.get("username")},
    )
    return JSONResponse(content={"key": metadata})


async def handle_delete_openai_api_key(
    request: Request,
    key_id: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    deleted = await api_context.dependencies.webui_manager.database_api_keys.delete_key(key_id)
    if deleted == 0:
        raise_not_found(request, "API key not found.")
    log_audit_event(request, "DELETE_OPENAI_API_KEY", key_id)
    return create_no_content_response()


async def handle_rotate_openai_api_key(
    request: Request,
    key_id: str,
    payload: OpenAIAPIKeyCreatePayload,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    webui_manager = api_context.dependencies.webui_manager
    primary_signing_secret = api_context.dependencies.auth_config.primary_signing_secret
    if primary_signing_secret is None:
        raise_service_unavailable(request, "Authentication secret key is not configured.")
    rotated = await rotate_openai_api_key(
        webui_manager.database_api_keys,
        key_id,
        label=payload.label,
        scopes=payload.scopes,
        created_by=current_user["id"],
        expires_in_days=payload.expires_in_days,
        expires_at_ms=payload.expires_at_ms,
        rotation_reminder_in_days=payload.rotation_reminder_in_days,
        default_ttl_days=webui_manager.key_default_ttl_days,
        default_rotation_days=webui_manager.key_default_rotation_days,
        secret_key=primary_signing_secret,
    )
    if not rotated:
        raise_not_found(request, "API key not found.")
    token_value = rotated.pop("key")
    metadata = serialize_api_key_entry(rotated)
    log_audit_event(
        request,
        "ROTATE_OPENAI_API_KEY",
        key_id,
        {"new_key_id": metadata["key_id"]},
    )
    return JSONResponse(
        content={"key": token_value, "metadata": metadata},
        status_code=status.HTTP_201_CREATED,
    )


async def handle_delete_all_openai_api_keys(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> dict[str, int]:
    removed = await api_context.dependencies.webui_manager.database_api_keys.delete_all_keys()
    log_audit_event(request, "PURGE_OPENAI_API_KEYS", "all", {"deleted": removed})
    return {"deleted": removed}


async def handle_get_openai_api_key_quota(
    request: Request,
    key_id: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    database_api_keys = api_context.dependencies.webui_manager.database_api_keys
    await webui_fetch_or_404(
        request,
        database_api_keys.get_key_by_id(key_id),
        message="API key not found.",
    )
    config = await database_api_keys.get_quota_config(key_id)
    quota_status = await database_api_keys.get_quota_status(key_id, epoch_ms())
    return JSONResponse(content={"key_id": key_id, "config": config, "status": quota_status})


async def handle_update_openai_api_key_quota(
    request: Request,
    key_id: str,
    payload: OpenAIAPIKeyQuotaUpdatePayload,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    database_api_keys = api_context.dependencies.webui_manager.database_api_keys
    await webui_fetch_or_404(
        request,
        database_api_keys.get_key_by_id(key_id),
        message="API key not found.",
    )
    updated_config = await database_api_keys.set_quota_config(
        key_id,
        payload.model_dump(exclude_none=True),
        reset_usage=True,
    )
    quota_status = await database_api_keys.get_quota_status(key_id, epoch_ms())
    log_audit_event(
        request,
        "UPDATE_OPENAI_API_KEY_QUOTA",
        key_id,
        {"updated_by": current_user.get("username"), "mode": updated_config.get("mode")},
    )
    return JSONResponse(
        content={
            "key_id": key_id,
            "config": updated_config,
            "status": quota_status,
        }
    )


async def handle_list_openai_api_key_quota_status(
    _request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    database_api_keys = api_context.dependencies.webui_manager.database_api_keys
    enriched = await list_quota_status_payload(database_api_keys)
    return JSONResponse(content={"keys": enriched})


def register_endpoints(router: APIRouter) -> None:
    router.get(
        "/openai-api-keys",
        dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
    )(handle_list_openai_api_keys)
    router.post(
        "/openai-api-keys",
        status_code=status.HTTP_201_CREATED,
        dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
    )(handle_create_openai_api_key)
    router.post(
        "/openai-api-keys/{key_id}/revoke",
        dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
    )(handle_revoke_openai_api_key)
    router.delete(
        "/openai-api-keys/{key_id}",
        status_code=204,
        dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
    )(handle_delete_openai_api_key)
    router.post(
        "/openai-api-keys/{key_id}/rotate",
        status_code=status.HTTP_201_CREATED,
        dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
    )(handle_rotate_openai_api_key)
    router.delete(
        "/openai-api-keys",
        dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
    )(handle_delete_all_openai_api_keys)
    router.get(
        "/openai-api-keys/{key_id}/quota",
        dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
    )(handle_get_openai_api_key_quota)
    router.patch(
        "/openai-api-keys/{key_id}/quota",
        dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
    )(handle_update_openai_api_key_quota)
    router.get(
        "/openai-api-keys/quota/status",
        dependencies=require_action_dependencies(AccessAction.OPENAI_API_ADMIN),
    )(handle_list_openai_api_key_quota_status)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.webui)
