"""SoAI - Plugin package download command handler [backend/plugins/actions/plugin_package_download.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_plugins import DownloadPluginPackageCommand
from core.progress.formatting import format_transfer_details
from plugins.action_response import PluginActionResponse
from plugins.actions.progress import (
    create_task_progress_sender,
    send_completion_with_task_for_plugin_manager,
)
from plugins.context_ids import resolve_task_id_from_context
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.download_execution import execute_plugin_download
from plugins.state.download_request_validation import prepare_plugin_download

__all__ = ("process_plugin_package_download_async",)

OPERATION_PLUGIN_PACKAGE_DOWNLOAD = "plugin_actions.plugin_package_download"


def _is_cancelled_status(status_code: int, error_type: str | None) -> bool:
    if status_code == 499:
        return True
    return isinstance(error_type, str) and error_type.strip().lower() == "cancelled"


async def _send_download_failure(
    manager: PluginManagerRuntimeProtocol,
    command: DownloadPluginPackageCommand,
    task_id: str | None,
    *,
    message: str,
    error_code: int,
    cancelled: bool = False,
) -> None:
    await send_completion_with_task_for_plugin_manager(
        manager,
        command.reply_channel,
        task_id,
        success=False,
        cancelled=cancelled,
        message=message,
        error_code=error_code,
        error_message=message,
    )


async def _send_download_response(
    manager: PluginManagerRuntimeProtocol,
    command: DownloadPluginPackageCommand,
    task_id: str | None,
    response: PluginActionResponse,
) -> None:
    if response.success:
        manager.start_initial_reconciliation()
        payload = dict(response.payload or {})
        payload["status"] = "completed"
        await send_completion_with_task_for_plugin_manager(
            manager,
            command.reply_channel,
            task_id,
            success=True,
            message=str(payload.get("message") or "Plugin download completed."),
            result=payload,
        )
        return
    await _send_download_failure(
        manager,
        command,
        task_id,
        cancelled=_is_cancelled_status(response.status_code, response.error_type),
        message=response.error_message or "Plugin download failed.",
        error_code=response.status_code,
    )


async def process_plugin_package_download_async(
    manager: PluginManagerRuntimeProtocol,
    command: DownloadPluginPackageCommand,
) -> None:
    task_id = resolve_task_id_from_context(command.context)
    registry = manager.dependencies.infrastructure.task_registry
    progress = create_task_progress_sender(
        command.reply_channel,
        task_id,
        registry,
        manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
    )
    try:
        await progress(1, "Preparing plugin download")
        prep = await prepare_plugin_download(
            manager,
            command.url,
            enforce_initial_network_policy=False,
        )
        if isinstance(prep, PluginActionResponse):
            await _send_download_failure(
                manager,
                command,
                task_id,
                message=prep.error_message or "Plugin download failed.",
                error_code=prep.status_code,
            )
            return
        http_client = manager.http_client
        if http_client is None:
            await _send_download_failure(
                manager,
                command,
                task_id,
                message="Plugin download requires an HTTP client.",
                error_code=500,
            )
            return

        async def on_progress(
            bytes_written: int,
            declared_total: int | None,
            bytes_per_second: float,
            eta_seconds: float,
        ) -> None:
            percent = 5
            if declared_total is not None and declared_total > 0:
                percent = max(5, min(90, int(bytes_written / declared_total * 90)))
            details = format_transfer_details(
                bytes_written,
                declared_total,
                speed=bytes_per_second,
                eta_seconds=eta_seconds,
            )
            await progress(percent, f"Downloading {prep.filename}", details)

        response = await execute_plugin_download(
            manager=manager,
            prep=prep,
            temp_directory=manager.paths.temp_directory,
            cancellation_token_scope=manager.dependencies.infrastructure.task_helpers.cancellation_token_scope,
            logger=manager.logger,
            context=command.context,
            http_client=http_client,
            on_progress=on_progress,
        )
        await _send_download_response(manager, command, task_id, response)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            manager.logger,
            exception,
            message="Plugin package download failed.",
            operation=OPERATION_PLUGIN_PACKAGE_DOWNLOAD,
            details={"url": command.url, "task_id": task_id},
        )
        await _send_download_failure(
            manager,
            command,
            task_id,
            message=str(exception) or "Plugin download failed.",
            error_code=500,
        )
