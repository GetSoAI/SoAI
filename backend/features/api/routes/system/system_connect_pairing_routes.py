"""SoAI - SoAI Connect pairing details route [backend/features/api/routes/system/system_connect_pairing_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Depends, Request
from starlette.responses import Response

from core.errors.exceptions import ValidationError
from core.meta.instance_identity import resolve_instance_identity
from core.network.interface_addresses import classify_bind_scope, list_connect_addresses
from core.state.access import AccessAction
from core.types.json import JSONDict
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.response_body import create_json_body_response

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.system.get(
        "/connect-pairing",
        dependencies=require_action_dependencies(AccessAction.AUTH_COOKIE),
    )
    async def system_connect_pairing(
        _request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        runtime_api_endpoint = api_context.dependencies.runtime_state.runtime_api_endpoint
        if runtime_api_endpoint is None:
            raise ValidationError("Runtime API endpoint is unavailable.")
        identity = await resolve_instance_identity(
            api_context.dependencies.database_plugins,
            api_context.dependencies.database_licensing,
        )
        addresses = await asyncio.to_thread(
            list_connect_addresses,
            runtime_api_endpoint.bind_host,
        )
        payload: JSONDict = {
            "scheme": runtime_api_endpoint.scheme,
            "port": runtime_api_endpoint.effective_port,
            "instance_id": identity.instance_id,
            "bind_scope": classify_bind_scope(runtime_api_endpoint.bind_host),
            "addresses": list(addresses),
        }
        return create_json_body_response(content=payload, no_store=True)
