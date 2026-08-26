"""SoAI - Plugin upload routes [backend/features/api/routes/plugins/plugin_upload_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from core.files.operations import async_remove
from core.logging.trace import get_logger
from core.plugins.protocols_instance import PluginStagedUploadProtocol
from core.state.access import AccessAction
from core.tasks.type_catalog import TASK_TYPE_PLUGIN_UPLOAD
from features.api.routes.plugins.plugin_task_api_response import (
    raise_prepared_plugin_task_error,
)
from features.api.routes.plugins.plugin_task_cancellation import (
    cancel_task_after_request_cancellation,
)
from features.api.routes.plugins.plugin_task_preparation import (
    prepare_plugin_task_for_request,
)
from features.api.routes.upload_streaming_multipart_models import StreamingStagedPart
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
)
from features.api.routes.upload_streaming_single_file_request import (
    SingleFileUploadRequestSpec,
    stage_single_file_upload_request,
)
from features.api.runtime.access_dependencies import restart_protected_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import raise_forbidden
from features.api.runtime.responses import create_task_accepted_response

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.plugin_upload_routes"


@dataclass(frozen=True, slots=True)
class _StagedPluginUpload(PluginStagedUploadProtocol):
    original_filename: str
    temp_path: str
    size_bytes: int


async def _stage_plugin_upload(
    request: Request,
    api_context: ApiContext,
) -> StreamingStagedPart:
    staged = await stage_single_file_upload_request(
        request,
        api_context=api_context,
        spec=SingleFileUploadRequestSpec(
            subsystem="plugin_upload",
            owner="plugin_upload",
            logger=get_logger(LOGGER_NAME),
            reservation_purpose=StreamingUploadReservationPurpose(
                declared_operation="api_plugin.upload.stage",
                chunk_operation="api_plugin.upload.stage_chunk",
                declared_details={"purpose": "plugin_upload_temp_file"},
                chunk_details={"purpose": "plugin_upload_temp_file"},
            ),
            required_fields=frozenset(),
            allowed_fields=frozenset(),
        ),
    )
    return staged.parsed.files[0]


async def _remove_staged_upload(path: str) -> None:
    try:
        await async_remove(path)
    except FileNotFoundError:
        return


def register_routes(routers: ApiRouters) -> None:
    @routers.plugins.post(
        "/upload",
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
    )
    async def upload_plugin(
        request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        plugin_manager_instance = api_context.dependencies.plugin_manager
        if not plugin_manager_instance.uploads_enabled:
            raise_forbidden(
                request,
                error_type="uploads_disabled",
                message="Plugin uploads are disabled by the administrator.",
            )
        staged = await _stage_plugin_upload(request, api_context)
        staged_path: str | None = staged.temp_path
        filename = staged.original_filename
        try:
            log_audit_event(request, "UPLOAD_PLUGIN", filename)
            prepared_task = await prepare_plugin_task_for_request(
                request,
                api_context=api_context,
                task_type=TASK_TYPE_PLUGIN_UPLOAD,
                status_message="Uploading plugin package",
                metadata={"operation": "plugin_upload", "filename": filename},
            )
            upload = _StagedPluginUpload(
                original_filename=filename,
                temp_path=staged.temp_path,
                size_bytes=staged.size_bytes,
            )
            staged_path = None
            try:
                response = await plugin_manager_instance.upload_staged_plugin_package(
                    upload,
                    prepared_task.context,
                )
            except asyncio.CancelledError:
                await cancel_task_after_request_cancellation(
                    registry=prepared_task.registry,
                    task_id=prepared_task.task_id,
                    context=prepared_task.context,
                    operation="api_plugin.upload_plugin.cancel_task",
                    trace_id=prepared_task.trace_id,
                )
                raise
            if response.success:
                return create_task_accepted_response(
                    task_id=prepared_task.task_id,
                    commit_deadline_ts_ms=None,
                    extra=response.payload,
                )
            await raise_prepared_plugin_task_error(
                request,
                prepared_task=prepared_task,
                status_code=response.status_code,
                error_type=response.error_type or "plugin_upload_failed",
                error_message=response.error_message or "Plugin upload failed.",
                operation="api_plugin.upload_plugin.fail_task",
                details={"filename": filename},
                extra=response.extra,
            )
        finally:
            if staged_path is not None:
                await _remove_staged_upload(staged_path)
