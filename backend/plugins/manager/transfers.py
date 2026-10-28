"""SoAI - Plugin package transfers and download tracking [backend/plugins/manager/transfers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.models.discovery_trigger import publish_model_discovery_request
from core.runtime.request_context import RequestContext
from core.types.protocols import HttpClientProtocol
from plugins.action_response import PluginActionResponse
from plugins.manager.transfer_outcomes import (
    ModelDiscoveryQueueStatus,
    ModelDownloadFinalization,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "download_plugin_package",
    "finalize_model_download",
    "is_model_download_in_progress",
    "mark_discovery_pending_after_download",
    "register_model_download",
)

LOGGER_NAME = "SoAI.plugins.manager.transfers"
OPERATION_FINALIZE_MODEL_DOWNLOAD = "plugins.manager.transfers.finalize_model_download"


async def is_model_download_in_progress(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> bool:
    async with self.state.download.download_state_lock:
        return plugin_name in self.state.download.plugins_with_active_downloads


async def mark_discovery_pending_after_download(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    async with self.state.download.download_state_lock:
        if plugin_name in self.state.download.plugins_with_active_downloads:
            self.state.download.pending_discovery_after_download.add(plugin_name)


async def register_model_download(self: PluginManagerRuntimeProtocol, plugin_name: str) -> None:
    async with self.state.download.download_state_lock:
        self.state.download.plugins_with_active_downloads.add(plugin_name)


async def finalize_model_download(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    context: RequestContext | None,
    discovery_requested: bool,
) -> ModelDownloadFinalization:
    pending_trigger = False
    async with self.state.download.download_state_lock:
        self.state.download.plugins_with_active_downloads.discard(plugin_name)
        pending_trigger = plugin_name in self.state.download.pending_discovery_after_download
        self.state.download.pending_discovery_after_download.discard(plugin_name)
    if not (discovery_requested or pending_trigger):
        return ModelDownloadFinalization(ModelDiscoveryQueueStatus.NOT_REQUESTED)
    try:
        await publish_model_discovery_request(
            self.dependencies.infrastructure.event_bus,
            plugins_to_scan=[plugin_name],
            context=context,
            wait_for_completion=False,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Model discovery was deferred after model download.",
            operation=OPERATION_FINALIZE_MODEL_DOWNLOAD,
            details={"plugin_name": plugin_name, "discovery_status": "deferred"},
            level="warning",
        )
        return ModelDownloadFinalization(ModelDiscoveryQueueStatus.DEFERRED)
    return ModelDownloadFinalization(ModelDiscoveryQueueStatus.QUEUED)


async def download_plugin_package(
    self: PluginManagerRuntimeProtocol,
    url: str,
    context: RequestContext,
    http_client: HttpClientProtocol,
) -> PluginActionResponse:
    response = await self.state.download.download_agent.download_package(
        self,
        url,
        context,
        http_client,
    )
    if response.success:
        self.start_initial_reconciliation()
    return response
