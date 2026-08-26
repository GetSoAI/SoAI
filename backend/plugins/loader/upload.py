"""SoAI - Plugin package upload validation and installation handoff [backend/plugins/loader/upload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_plugins import UploadPluginCommand
from core.files.operations import async_remove
from core.logging.trace import get_logger
from core.plugins.file_suffixes import PLUGIN_FILE_SUFFIX
from core.plugins.protocols_instance import PluginStagedUploadProtocol
from core.runtime.request_context import RequestContext, create_system_context
from plugins.action_response import (
    PluginActionResponse,
    accepted_plugin_action_response,
)
from plugins.path_safety import normalize_plugin_filename
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.responses import build_invalid_filename_response

__all__ = ("upload_staged_plugin_package",)

LOGGER_NAME = "SoAI.plugins.loader.upload"
OPERATION = "plugin_loader.upload_plugin"
UPLOAD_STAGING_EXCEPTIONS: tuple[type[Exception], ...] = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)


async def _remove_staged_plugin_file(temp_file_path: str) -> None:
    try:
        await async_remove(temp_file_path)
    except FileNotFoundError:
        return


async def upload_staged_plugin_package(
    manager: PluginManagerRuntimeProtocol,
    upload: PluginStagedUploadProtocol,
    context: RequestContext | None,
) -> PluginActionResponse:
    logger = get_logger(LOGGER_NAME)
    temp_file_path = upload.temp_path
    owns_staged_file = True
    try:
        if not manager.state.configuration.uploads_enabled:
            return PluginActionResponse(
                success=False,
                status_code=403,
                error_type="uploads_disabled",
                error_message="Plugin uploads are disabled by the administrator.",
            )
        filename = upload.original_filename.strip()
        if not filename:
            return PluginActionResponse(
                success=False,
                status_code=400,
                error_type="invalid_file_type",
                error_message=(f"Invalid file type. Only {PLUGIN_FILE_SUFFIX} files are allowed."),
            )
        try:
            plugin_name, _plugin_destination_path = normalize_plugin_filename(
                manager,
                filename,
            )
        except ValidationError as exception:
            return build_invalid_filename_response(exception)
        effective_context = context or create_system_context("plugin_upload")
        if upload.size_bytes <= 0:
            raise ValidationError("Uploaded plugin file is empty.")
        actual_size = await asyncio.to_thread(os.path.getsize, temp_file_path)
        if actual_size != upload.size_bytes:
            raise ValidationError("Staged plugin size changed before installation handoff.")
        reply_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)
        await manager.dependencies.infrastructure.event_bus.publish(
            UploadPluginCommand(
                temp_file_path=temp_file_path,
                original_filename=filename,
                reply_channel=reply_queue,
                context=effective_context,
            ),
        )
        owns_staged_file = False
        return accepted_plugin_action_response(
            {
                "status": "accepted",
                "filename": filename,
                "plugin_name": plugin_name,
            },
        )
    except asyncio.CancelledError:
        try:
            await uncancel_then_cleanup(_remove_staged_plugin_file(temp_file_path))
        finally:
            owns_staged_file = False
        raise
    except UPLOAD_STAGING_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message="Error during staged plugin upload.",
            operation=OPERATION,
            details={"filename": upload.original_filename},
        )
        if isinstance(exception, ValidationError):
            return PluginActionResponse(
                success=False,
                status_code=400,
                error_type="upload_error",
                error_message=str(exception.message),
            )
        return PluginActionResponse(
            success=False,
            status_code=coerced.http_status,
            error_type=str(coerced.code),
            error_message="Plugin upload failed before installation handoff.",
        )
    finally:
        if owns_staged_file:
            await _remove_staged_plugin_file(temp_file_path)
