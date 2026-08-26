"""SoAI - Plugin download routes [backend/features/api/routes/plugins/plugin_download_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Depends, Request, status
from fastapi.responses import JSONResponse

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_plugins import DownloadPluginPackageCommand
from core.logging.trace import get_logger
from core.runtime.network_policy import OfflineModeError, validate_local_only_url
from core.state.access import AccessAction
from core.tasks.type_catalog import TASK_TYPE_PLUGIN_DOWNLOAD
from features.api.routes.plugins.plugin_task_api_response import (
    raise_prepared_plugin_task_error,
)
from features.api.routes.plugins.plugin_task_preparation import (
    prepare_plugin_task_for_request,
)
from features.api.runtime.access_dependencies import restart_protected_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.responses import create_task_accepted_response
from features.api.schemas.plugins import PluginDownloadRequest

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.plugin_download_routes"
OPERATION_PLUGIN_DOWNLOAD_PUBLISH = "api_plugin.download_plugin.publish"


def register_routes(routers: ApiRouters) -> None:
    @routers.plugins.post(
        "/download",
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
    )
    async def download_plugin(
        request: Request,
        payload: PluginDownloadRequest,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        plugin_manager_instance = api_context.dependencies.plugin_manager
        url = str(payload.url)
        prepared_task = await prepare_plugin_task_for_request(
            request,
            api_context=api_context,
            task_type=TASK_TYPE_PLUGIN_DOWNLOAD,
            status_message="Downloading plugin package",
            metadata={"operation": "plugin_download", "url": url},
        )
        if not plugin_manager_instance.downloads_enabled:
            await raise_prepared_plugin_task_error(
                request,
                prepared_task=prepared_task,
                status_code=status.HTTP_403_FORBIDDEN,
                error_type="downloads_disabled",
                error_message="Plugin downloads are disabled by the administrator.",
                operation="api_plugin.download_plugin.downloads_disabled",
                details={"url": url},
            )
        try:
            await validate_local_only_url(
                api_context.dependencies.runtime_flags,
                url,
                source="plugin download",
            )
        except OfflineModeError as exception:
            await raise_prepared_plugin_task_error(
                request,
                prepared_task=prepared_task,
                status_code=status.HTTP_423_LOCKED,
                error_type="offline_mode",
                error_message=str(exception),
                operation="api_plugin.download_plugin.offline",
                details={"url": url},
            )
        log_audit_event(request, "DOWNLOAD_PLUGIN", url)
        reply_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)
        try:
            await plugin_manager_instance.dependencies.infrastructure.event_bus.publish(
                DownloadPluginPackageCommand(
                    url=url,
                    reply_channel=reply_queue,
                    context=prepared_task.context,
                ),
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Failed to schedule plugin download.",
                operation=OPERATION_PLUGIN_DOWNLOAD_PUBLISH,
                trace_id=prepared_task.trace_id,
                details={"url": url, "task_id": prepared_task.task_id},
            )
            await raise_prepared_plugin_task_error(
                request,
                prepared_task=prepared_task,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_type="plugin_download_schedule_failed",
                error_message="Failed to schedule plugin download.",
                operation="api_plugin.download_plugin.publish_failed",
                details={"url": url},
            )
        return create_task_accepted_response(
            task_id=prepared_task.task_id,
            commit_deadline_ts_ms=None,
            extra={"url": url},
        )
