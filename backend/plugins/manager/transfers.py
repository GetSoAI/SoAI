"""SoAI - Plugin package transfers and download tracking [backend/plugins/manager/transfers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.payload import ErrorPublicPayload
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.models.discovery_trigger import publish_model_discovery_request
from core.runtime.network_policy import require_online_mode
from core.runtime.request_context import RequestContext
from core.types.json import is_json_dict
from core.types.protocols import HttpClientProtocol
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.action_response import PluginActionResponse
from plugins.manager.capability_support import supports_plugin_capability_from_instance
from plugins.manager.load_serialization import serialized_plugin_load_scope
from plugins.manager.transfer_outcomes import (
    ModelDiscoveryQueueStatus,
    ModelDownloadFinalization,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.types.json import JSONDict

__all__ = (
    "check_for_backend_updates",
    "download_plugin_package",
    "finalize_model_download",
    "is_model_download_in_progress",
    "mark_discovery_pending_after_download",
    "register_model_download",
)

LOGGER_NAME = "SoAI.plugins.manager.transfers"
OPERATION_FINALIZE_MODEL_DOWNLOAD = "plugins.manager.transfers.finalize_model_download"
UPDATE_CHECK_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    RuntimeError,
)


def _build_update_check_error(reason: str) -> JSONDict:
    return {
        "update_available": False,
        "error": ErrorPublicPayload(
            code="server_error",
            message="Update check failed.",
            details={"reason": reason},
        ).to_dict(),
    }


def _build_update_check_not_supported() -> JSONDict:
    return {
        "update_available": False,
        "error": ErrorPublicPayload(
            code="not_implemented",
            message="Update check not supported.",
        ).to_dict(),
    }


def _is_backend_update_check_candidate(plugin: JSONDict) -> bool:
    if not coerce_bool_with_recovery(
        plugin,
        "installed",
        logger=get_logger(LOGGER_NAME),
        operation="plugins.manager.transfers.coerce_bool_flag",
        default=False,
    ):
        return False
    if not coerce_bool_with_recovery(
        plugin,
        "is_available",
        logger=get_logger(LOGGER_NAME),
        operation="plugins.manager.transfers.coerce_bool_flag",
        default=False,
    ):
        return False
    capabilities = plugin.get("capabilities")
    if not is_json_dict(capabilities):
        return False
    return coerce_bool_with_recovery(
        capabilities,
        "supports_backend_installation",
        logger=get_logger(LOGGER_NAME),
        operation="plugins.manager.transfers.coerce_bool_flag",
        default=False,
    )


async def _check_instance_for_backend_update(
    instance: PluginInstanceProtocol,
) -> tuple[str, JSONDict]:
    if not supports_plugin_capability_from_instance(
        instance,
        "SUPPORTS_BACKEND_INSTALLATION",
    ):
        return instance.plugin_name, _build_update_check_not_supported()
    try:
        if supports_plugin_capability_from_instance(instance, "SUPPORTS_CONFIGURATION"):
            await instance.refresh_runtime_configuration()
        result = await instance.check_for_backend_update()
    except UPDATE_CHECK_EXCEPTIONS as exception:
        return instance.plugin_name, _build_update_check_error(str(exception))
    if isinstance(result, dict):
        return instance.plugin_name, result
    return (
        instance.plugin_name,
        {
            "update_available": False,
            "error": ErrorPublicPayload(
                code="invalid_response",
                message="Update check returned invalid payload.",
                details={"plugin": instance.plugin_name},
            ).to_dict(),
        },
    )


async def _load_and_check_plugin_for_backend_update(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> tuple[str, JSONDict]:
    async with serialized_plugin_load_scope(self, plugin_name):
        try:
            instance = await self.require_loaded_plugin(plugin_name, auto_load=True)
        except UPDATE_CHECK_EXCEPTIONS as exception:
            return plugin_name, _build_update_check_error(str(exception))
        return await _check_instance_for_backend_update(instance)


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


async def check_for_backend_updates(
    self: PluginManagerRuntimeProtocol,
) -> dict[str, JSONDict]:
    self.dependencies.infrastructure.lifecycle.require_enabled("Plugin manager")
    require_online_mode(
        self.dependencies.infrastructure.runtime_flags,
        source="plugin backend update check",
    )
    installed = await self.list_plugins()
    listed_plugin_names = [
        plugin_name
        for plugin in installed
        if isinstance((plugin_name := plugin.get("name")), str) and plugin_name
    ]
    updates: dict[str, JSONDict] = {
        plugin_name: _build_update_check_not_supported() for plugin_name in listed_plugin_names
    }
    names: list[str] = []
    for plugin in installed:
        if not _is_backend_update_check_candidate(plugin):
            continue
        plugin_name = plugin.get("name")
        if isinstance(plugin_name, str) and plugin_name:
            names.append(plugin_name)
    if not names:
        return updates
    results = await asyncio.gather(
        *[_load_and_check_plugin_for_backend_update(self, name) for name in names],
        return_exceptions=False,
    )
    for plugin_name, result in results:
        updates[plugin_name] = result
    return updates
