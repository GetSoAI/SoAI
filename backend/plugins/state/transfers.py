"""SoAI - Plugin download and filesystem safety manager [backend/plugins/state/transfers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

import httpx2

from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import TraceLogger
from core.runtime.network_policy import OfflineModeError
from core.runtime.request_context import RequestContext
from core.tasks.protocols import CancellationTokenScopeCallable
from core.types.protocols import HttpClientProtocol
from plugins.action_response import PluginActionResponse
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginDownloadManagerProtocol,
)
from plugins.state.download_execution import execute_plugin_download
from plugins.state.download_online_mode import build_plugin_download_offline_mode_response
from plugins.state.download_request_validation import prepare_plugin_download

__all__ = (
    "PluginDownloadAgent",
    "PluginDownloadAgentDependencies",
)

OPERATION_PLUGIN_STATE_DOWNLOAD_AGENT_DOWNLOAD_PACKAGE = (
    "plugin_state.download_agent.download_package"
)


@dataclass(frozen=True, slots=True)
class PluginDownloadAgentDependencies:
    temp_directory: str
    logger: TraceLogger
    cancellation_token_scope: CancellationTokenScopeCallable

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginDownloadAgentDependencies",
            cancellation_token_scope=self.cancellation_token_scope,
            logger=self.logger,
            temp_directory=self.temp_directory,
        )


class PluginDownloadAgent:
    def __init__(self, deps: PluginDownloadAgentDependencies) -> None:
        self._deps = deps

    async def download_package(
        self,
        manager: PluginDownloadManagerProtocol,
        url: str,
        context: RequestContext | None,
        http_client: HttpClientProtocol,
    ) -> PluginActionResponse:
        operation = "plugin_state.download_agent.download_package"
        try:
            prep = await prepare_plugin_download(
                manager,
                url,
                enforce_initial_network_policy=False,
            )
            if isinstance(prep, PluginActionResponse):
                return prep
            return await execute_plugin_download(
                manager=manager,
                prep=prep,
                temp_directory=self._deps.temp_directory,
                cancellation_token_scope=self._deps.cancellation_token_scope,
                logger=self._deps.logger,
                context=context,
                http_client=http_client,
            )
        except OfflineModeError as exception:
            return build_plugin_download_offline_mode_response(exception)
        except httpx2.HTTPStatusError as exception:
            status_code = int(exception.response.status_code)
            return PluginActionResponse(
                success=False,
                status_code=status_code,
                error_type="download_failed",
                error_message=f"Download failed. Server responded with status {status_code}.",
            )
        except httpx2.RequestError as exception:
            return PluginActionResponse(
                success=False,
                status_code=503,
                error_type="download_failed",
                error_message=f"A network error occurred during download: {exception}",
            )
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=operation)
            log_exception(
                self._deps.logger,
                coerced,
                message="Unexpected error during plugin download.",
                operation=OPERATION_PLUGIN_STATE_DOWNLOAD_AGENT_DOWNLOAD_PACKAGE,
                details={"url": url},
            )
            return PluginActionResponse(
                success=False,
                status_code=500,
                error_type="server_error",
                error_message=f"An unexpected error occurred: {exception}",
            )
