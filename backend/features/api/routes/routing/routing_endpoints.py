"""SoAI - Virtual model routing configuration API endpoints [backend/features/api/routes/routing/routing_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse, Response

from core.errors.exceptions import ValidationError
from core.events.types_models_routing_commands import UpdateRoutingConfigCommand
from core.orchestrator.routing_config import ConstituentModelConfig
from core.runtime.protocols import RequestProtocol
from core.serialization.json import normalize_for_json
from core.state.access import AccessAction
from core.types.json_value import coerce_json_dict
from features.api.routes.routing.routing_snapshot import fetch_routing_config_snapshot
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import (
    raise_gateway_timeout,
    raise_invalid_request,
    raise_not_found,
    raise_server_error,
)
from features.api.schemas.virtual_models import (
    ConstituentModel,
    VirtualModelCreate,
    VirtualModelEnabledUpdate,
    VirtualModelUpdate,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "create_virtual_model",
    "get_routing_config",
    "list_virtual_models",
    "register_endpoints",
    "register_routes",
    "virtual_model_delete",
    "virtual_model_get",
    "virtual_model_set_enabled",
    "virtual_model_update",
)


async def _get_routing_config_snapshot(
    request: RequestProtocol,
    api_context: ApiContext,
) -> JSONDict:
    try:
        return await fetch_routing_config_snapshot(
            event_bus=api_context.dependencies.event_bus,
            context=request.state.context,
        )
    except TimeoutError:
        raise_gateway_timeout(
            request,
            "Orchestrator did not respond in time.",
        )


async def _get_virtual_models_snapshot(
    request: RequestProtocol,
    api_context: ApiContext,
) -> list[JSONDict]:
    routing_config_snapshot = await _get_routing_config_snapshot(
        request,
        api_context,
    )
    virtual_models_value = routing_config_snapshot.get("virtual_models")
    if not isinstance(virtual_models_value, list):
        return []
    virtual_models: list[JSONDict] = []
    for entry in virtual_models_value:
        virtual_model = coerce_json_dict(entry)
        if virtual_model is not None:
            virtual_models.append(virtual_model)
    return virtual_models


def _require_virtual_model_name(request: RequestProtocol, name: str) -> str:
    normalized_name = (name or "").strip()
    if not normalized_name:
        raise_invalid_request(request, "A virtual model name must be provided.")
    return normalized_name


async def _validate_virtual_model_constituents(
    request: Request,
    api_context: ApiContext,
    models: list[ConstituentModel],
) -> None:
    try:
        await api_context.dependencies.model_virtual_model_service.virtual_model_validate_constituents(
            [
                ConstituentModelConfig(
                    universal_id=model.universal_id,
                    parameters=model.parameters or {},
                )
                for model in models
            ],
        )
    except (ValidationError, ValueError) as exception:
        raise_invalid_request(request, str(exception))


def _require_existing_virtual_model(
    request: Request,
    api_context: ApiContext,
    name: str,
) -> None:
    virtual_model = api_context.dependencies.model_virtual_model_service.virtual_model_get(
        name,
    )
    if virtual_model is None:
        raise_not_found(request, f"Virtual model '{name}' not found.")


async def get_routing_config(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    snapshot = await _get_routing_config_snapshot(request, api_context)
    return JSONResponse(content=snapshot)


async def list_virtual_models(
    request: Request,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    snapshot = await _get_virtual_models_snapshot(request, api_context)
    return JSONResponse(content=snapshot)


async def virtual_model_get(
    request: Request,
    name: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    normalized_name = _require_virtual_model_name(request, name)
    virtual_model = api_context.dependencies.model_virtual_model_service.virtual_model_get(
        normalized_name,
    )
    if not virtual_model:
        raise_not_found(request, f"Virtual model '{normalized_name}' not found.")
    raw = asdict(virtual_model)
    normalized = normalize_for_json(raw)
    virtual_model_json = coerce_json_dict(normalized)
    if virtual_model_json is None:
        raise_server_error(request, "Virtual model response is invalid.")
    return JSONResponse(content=virtual_model_json)


async def create_virtual_model(
    request: Request,
    payload: VirtualModelCreate,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    await _validate_virtual_model_constituents(request, api_context, payload.models)
    return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
        request,
        UpdateRoutingConfigCommand,
        "final",
        "CREATE_VIRTUAL_MODEL",
        payload.name,
        {"strategy": payload.strategy},
        {
            "action": "add",
            "entity_type": "virtual_model",
            "data": payload.model_dump(),
        },
    )


async def virtual_model_update(
    request: Request,
    name: str,
    payload: VirtualModelUpdate,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    normalized_name = _require_virtual_model_name(request, name)
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise_invalid_request(request, "No update data provided.")
    _require_existing_virtual_model(request, api_context, normalized_name)
    if payload.models:
        await _validate_virtual_model_constituents(request, api_context, payload.models)
    return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
        request,
        UpdateRoutingConfigCommand,
        "final",
        "UPDATE_VIRTUAL_MODEL",
        normalized_name,
        {"updates": update_data},
        {
            "action": "update",
            "entity_type": "virtual_model",
            "data": {"name": normalized_name, **update_data},
        },
    )


async def virtual_model_set_enabled(
    request: Request,
    name: str,
    payload: VirtualModelEnabledUpdate,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    normalized_name = _require_virtual_model_name(request, name)
    _require_existing_virtual_model(request, api_context, normalized_name)
    return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
        request,
        UpdateRoutingConfigCommand,
        "final",
        "SET_VIRTUAL_MODEL_ENABLED",
        normalized_name,
        {"enabled": payload.enabled},
        {
            "action": "set_enabled",
            "entity_type": "virtual_model",
            "data": {"name": normalized_name, "enabled": payload.enabled},
        },
    )


async def virtual_model_delete(
    request: Request,
    name: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    normalized_name = _require_virtual_model_name(request, name)
    _require_existing_virtual_model(request, api_context, normalized_name)
    return await api_context.dependencies.command_dispatcher.dispatch_and_respond(
        request,
        UpdateRoutingConfigCommand,
        "final",
        "DELETE_VIRTUAL_MODEL",
        normalized_name,
        command_fields={
            "action": "remove",
            "entity_type": "virtual_model",
            "data": {"name": normalized_name},
        },
    )


def register_endpoints(router: APIRouter) -> None:
    routing_read_deps = require_action_dependencies(AccessAction.MODEL_ROUTING_READ)
    restart_model_routing_deps = tuple(
        restart_protected_dependencies(AccessAction.MODEL_ROUTING_ADMIN),
    )
    router.get("/config", dependencies=routing_read_deps)(get_routing_config)
    router.get("/virtual-models", dependencies=routing_read_deps)(list_virtual_models)
    router.get("/virtual-models/{name:path}", dependencies=routing_read_deps)(virtual_model_get)
    router.post(
        "/virtual-models",
        status_code=201,
        dependencies=restart_model_routing_deps,
    )(create_virtual_model)
    router.patch(
        "/virtual-models/{name:path}/enabled",
        status_code=200,
        dependencies=restart_model_routing_deps,
    )(virtual_model_set_enabled)
    router.patch(
        "/virtual-models/{name:path}",
        status_code=200,
        dependencies=restart_model_routing_deps,
    )(virtual_model_update)
    router.delete(
        "/virtual-models/{name:path}",
        status_code=200,
        dependencies=restart_model_routing_deps,
    )(virtual_model_delete)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.routing)
