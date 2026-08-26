"""SoAI - Plugin manager transfer operations [backend/plugins/manager/transfer_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.protocols_instance import PluginStagedUploadProtocol
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict
from core.types.protocols import HttpClientProtocol
from core.validation.strings import require_trimmed_text
from plugins.action_response import PluginActionResponse
from plugins.loader.upload import upload_staged_plugin_package
from plugins.manager.name_normalization import (
    call_with_optional_plugin_name,
    call_with_required_plugin_name,
    normalize_optional_plugin_name,
)
from plugins.manager.transfer_outcomes import (
    ModelDiscoveryQueueStatus,
    ModelDownloadFinalization,
)
from plugins.manager.transfers import (
    check_for_backend_updates,
    download_plugin_package,
    finalize_model_download,
    is_model_download_in_progress,
    mark_discovery_pending_after_download,
    register_model_download,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = ("PluginManagerTransferOperations",)


class PluginManagerTransferOperations:
    async def mark_discovery_pending_after_download(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
    ) -> None:
        await call_with_optional_plugin_name(
            self,
            plugin_name,
            None,
            mark_discovery_pending_after_download,
        )

    async def finalize_model_download(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
        *,
        context: RequestContext | None,
        discovery_requested: bool,
    ) -> ModelDownloadFinalization:
        normalized_plugin_name = normalize_optional_plugin_name(self, plugin_name)
        if normalized_plugin_name is None:
            return ModelDownloadFinalization(ModelDiscoveryQueueStatus.NOT_REQUESTED)
        return await finalize_model_download(
            self,
            normalized_plugin_name,
            context=context,
            discovery_requested=discovery_requested,
        )

    async def download_plugin_package(
        self: PluginManagerRuntimeProtocol,
        url: str,
        context: RequestContext,
        http_client: HttpClientProtocol,
    ) -> PluginActionResponse:
        normalized_url = require_trimmed_text(url, "url is required.")
        return await download_plugin_package(self, normalized_url, context, http_client)

    async def upload_staged_plugin_package(
        self: PluginManagerRuntimeProtocol,
        upload: PluginStagedUploadProtocol,
        context: RequestContext,
    ) -> PluginActionResponse:
        return await upload_staged_plugin_package(self, upload, context)

    async def check_for_backend_updates(
        self: PluginManagerRuntimeProtocol,
    ) -> dict[str, JSONDict]:
        return await check_for_backend_updates(self)

    async def is_model_download_in_progress(
        self: PluginManagerRuntimeProtocol,
        plugin_name: str,
    ) -> bool:
        return await call_with_optional_plugin_name(
            self,
            plugin_name,
            False,
            is_model_download_in_progress,
        )

    async def register_model_download(self: PluginManagerRuntimeProtocol, plugin_name: str) -> None:
        await call_with_required_plugin_name(self, plugin_name, register_model_download)
