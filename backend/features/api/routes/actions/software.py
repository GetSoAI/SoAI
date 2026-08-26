"""SoAI - Software update routes [backend/features/api/routes/actions/software.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import httpx2
from fastapi import Depends, Request, status
from starlette.responses import JSONResponse, Response

from core.errors.exception_logging import log_exception
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import (
    raise_conflict,
    raise_offline_mode,
    raise_server_error,
    raise_service_unavailable,
)

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.software"
OPERATION = "api_actions.check_for_software_updates"


def register_routes(routers: ApiRouters) -> None:
    @routers.actions.post(
        "/software/check-for-updates",
        dependencies=require_action_dependencies(AccessAction.SOFTWARE_UPDATE),
    )
    async def check_for_software_updates(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        if api_context.dependencies.runtime_flags.offline_mode:
            raise_offline_mode(
                request,
                "SYSTEM.RUNTIME.STAY_OFFLINE is enabled. Software update checks are disabled.",
            )
        try:
            result = await api_context.dependencies.plugin_manager.updater.check_for_app_update()
            if not isinstance(result, dict):
                raise_server_error(request, "Update check returned an invalid response payload.")
            return JSONResponse(status_code=status.HTTP_200_OK, content=result)
        except httpx2.RequestError as exception:
            raise_service_unavailable(
                request,
                f"Could not fetch release info from GitHub: {exception}",
            )
        except (ValueError, TypeError) as exception:
            raise_server_error(
                request,
                f"Failed to process release information: {exception}",
                error_type="update_check_failed",
            )
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Software update check failed unexpectedly.",
                operation=OPERATION,
                level="warning",
            )
            raise_server_error(request, str(exception))

    @routers.software.post(
        "/update-soai",
        status_code=202,
        dependencies=restart_protected_dependencies(AccessAction.SOFTWARE_UPDATE),
    )
    async def update_soai_software(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        if api_context.dependencies.runtime_flags.offline_mode:
            raise_offline_mode(
                request,
                "SYSTEM.RUNTIME.STAY_OFFLINE is enabled. Software updates are disabled.",
            )
        log_audit_event(request, "TRIGGER_SELF_UPDATE", "soai_core")
        outcome, message = await api_context.dependencies.application_control.update()
        if outcome == "conflict":
            raise_conflict(request, message, error_type="update_in_progress")
        if outcome == "unavailable":
            raise_service_unavailable(request, message, error_type="update_unavailable")
        if outcome == "failed":
            raise_server_error(request, message, error_type="update_failed")
        if outcome != "accepted":
            raise_server_error(
                request,
                "Software update returned an invalid outcome.",
                error_type="update_failed",
            )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "accepted", "message": message},
        )
