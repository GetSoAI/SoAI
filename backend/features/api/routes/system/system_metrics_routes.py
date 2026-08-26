"""SoAI - System metrics and history management routes [backend/features/api/routes/system/system_metrics_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request

from core.state.access import AccessAction
from core.validation.booleans import parse_bool
from features.api.runtime.access_dependencies import restart_protected_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.system.post(
        "/hardware/history/reset",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.METRICS_RESET),
    )
    async def reset_hardware_history(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> dict[str, str]:
        log_audit_event(request, "RESET_HARDWARE_HISTORY", "hardware_history")
        await api_context.dependencies.hardware_soaibench.reset_history()
        if parse_bool(
            api_context.dependencies.config.get(
                "OBSERVABILITY.METRICS.RESET_GENESIS_ON_CLEAR",
                False,
            ),
            default=False,
        ):
            await api_context.dependencies.database_metrics.reset_genesis_uptime()
        return {"message": "Hardware history has been cleared from persistence."}
