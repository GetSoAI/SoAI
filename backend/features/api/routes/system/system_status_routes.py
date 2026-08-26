"""SoAI - System status and security posture routes [backend/features/api/routes/system/system_status_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.auth.cookies import determine_secure_cookie
from core.auth.openai_protection import OpenAIProtectionState
from core.errors.exceptions import ServiceUnavailableError, StateError
from core.meta.versioning import get_core_version
from core.serialization.json import normalize_for_json, normalize_to_json_dict
from core.state.access import AccessAction
from core.state.protocols import RestartStateManagerProtocol
from core.timing.epoch import epoch_ms
from features.api.middleware.security.anomaly_tracker import snapshot_anomaly_alert
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "collect_system_status_snapshot",
    "register_routes",
)


def _get_restart_state_snapshot(
    restart_state_manager: RestartStateManagerProtocol,
) -> JSONDict:
    if restart_state_manager is None:
        raise StateError("Restart state manager is not configured.")
    info = restart_state_manager.get_restart_info()
    if "required" not in info:
        raise StateError("Restart state manager returned incomplete data")
    return normalize_to_json_dict(
        normalize_for_json(info),
        message="Restart state snapshot is invalid.",
    )


def _collect_security_posture(
    api_context: ApiContext,
    request_scheme: str | None,
    *,
    openai_anonymous_mode_enabled: bool,
) -> JSONDict:
    config = api_context.dependencies.config
    security_snapshot = api_context.dependencies.security_runtime_state.snapshot()
    secure_transport_required = config.get_bool("SERVER.HTTP.SECURITY.REQUIRE_SECURE_TRANSPORT")
    proxy_alert_view = snapshot_anomaly_alert(api_context.dependencies.proxy_header_anomaly_tracker)
    if proxy_alert_view is None:
        proxy_alert_json: JSONDict | None = None
    elif isinstance(proxy_alert_view, dict):
        proxy_alert_json = normalize_to_json_dict(
            normalize_for_json(proxy_alert_view),
            message="Proxy anomaly snapshot is invalid.",
        )
    else:
        raise StateError("Proxy anomaly snapshot is invalid.")
    cookie_secure_configured = bool(determine_secure_cookie(config, request_scheme=None))
    cookie_secure_current_request = bool(
        determine_secure_cookie(config, request_scheme=request_scheme),
    )
    cookie_secure_https = bool(determine_secure_cookie(config, request_scheme="https"))
    if not isinstance(security_snapshot, dict):
        raise StateError("Security runtime state snapshot is invalid.")
    payload = dict(security_snapshot)
    payload["cookie_secure_configured"] = cookie_secure_configured
    payload["cookie_secure_current_request"] = cookie_secure_current_request
    payload["cookie_secure_over_https"] = cookie_secure_https
    payload["secure_transport_required"] = secure_transport_required
    payload["openai_anonymous_mode_enabled"] = openai_anonymous_mode_enabled
    payload["proxy_header_anomalies"] = proxy_alert_json
    return normalize_to_json_dict(
        normalize_for_json(payload),
        message="Security runtime state snapshot is invalid.",
    )


async def collect_system_status_snapshot(
    api_context: ApiContext,
    request_scheme: str | None = None,
    *,
    include_security: bool = False,
) -> JSONDict:
    orchestrator_instance = api_context.dependencies.orchestrator_control
    hardware_manager = api_context.dependencies.hw_manager
    state_aggregator = api_context.dependencies.state_aggregator
    if orchestrator_instance is None:
        raise StateError("Orchestrator control is not available for system status.")
    if state_aggregator is None:
        raise StateError("State aggregator is not available for system status.")
    if hardware_manager is None:
        raise ServiceUnavailableError("Hardware manager is not available for system status.")
    (
        (plugin_states, plugin_state_version),
        hw_info,
        orch_status,
        main_state_snapshot,
    ) = await asyncio.gather(
        state_aggregator.get_all_plugin_states_with_version(),
        hardware_manager.get_system_info(cache=True, include_gpu_capabilities=False),
        orchestrator_instance.get_status(),
        state_aggregator.get_main_state(),
        return_exceptions=False,
    )
    restart_info = _get_restart_state_snapshot(api_context.dependencies.restart_state_manager)
    main_state = main_state_snapshot.get("state") if isinstance(main_state_snapshot, dict) else None
    payload = {
        "timestamp_ms": epoch_ms(),
        "soai_version": get_core_version(),
        "main_state": main_state,
        "plugin_states": plugin_states,
        "plugin_state_version": plugin_state_version,
        "hardware": hw_info,
        "orchestrator": orch_status,
        "system_state": restart_info,
    }
    if include_security:
        protection_state = api_context.dependencies.webui_manager.database_api_keys.protection_state
        payload["security"] = _collect_security_posture(
            api_context,
            request_scheme,
            openai_anonymous_mode_enabled=(protection_state is OpenAIProtectionState.OPEN),
        )
    return normalize_to_json_dict(
        normalize_for_json(payload),
        message="System status snapshot is invalid.",
    )


def register_routes(routers: ApiRouters) -> None:
    status_read_deps = require_action_dependencies(AccessAction.SYSTEM_STATUS_READ)

    @routers.system.get("/status", dependencies=status_read_deps)
    async def get_system_status(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        snapshot = await collect_system_status_snapshot(
            api_context,
            request.url.scheme,
            include_security=False,
        )
        return JSONResponse(content=snapshot)

    @routers.system.get("/status/main", dependencies=status_read_deps)
    async def get_soai_main_status(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        state_snapshot = await api_context.dependencies.state_aggregator.get_main_state()
        payload: JSONDict = (
            normalize_to_json_dict(state_snapshot, message="Main state is invalid.")
            if isinstance(state_snapshot, dict)
            else {}
        )
        restart_info = _get_restart_state_snapshot(api_context.dependencies.restart_state_manager)
        payload["system_state"] = restart_info
        return JSONResponse(content=payload)

    @routers.system.get(
        "/security",
        dependencies=require_action_dependencies(AccessAction.ACL_ADMIN),
    )
    async def get_system_security(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        protection_state = api_context.dependencies.webui_manager.database_api_keys.protection_state
        return JSONResponse(
            content=_collect_security_posture(
                api_context,
                request.url.scheme,
                openai_anonymous_mode_enabled=(protection_state is OpenAIProtectionState.OPEN),
            ),
        )
