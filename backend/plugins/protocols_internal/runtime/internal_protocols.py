"""SoAI - Plugin manager runtime protocols [backend/plugins/protocols_internal/runtime/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Protocol

from core.logging.protocols import LoggerProtocol
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.runtime.startup_status import StartupPhaseResult
from plugins.action_response import PluginActionResponse
from plugins.manager.policy import PluginManagerPolicy
from plugins.protocols_internal.state.internal_protocols import (
    PluginDownloadManagerProtocol,
    PluginStateProtocol,
)

if TYPE_CHECKING:
    import httpx2

    from core.events.types_base import Event
    from core.hardware.protocols import HardwareManagerProtocol
    from core.models.remote_model_search_types import RemoteModelSearchResult
    from core.orchestrator.protocols_lifecycle import OrchestratorLifecycleProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.plugins.protocols_guardian import UpdaterModuleDependenciesProtocol
    from core.plugins.protocols_instance import PluginStagedUploadProtocol
    from core.plugins.protocols_lifecycle import PluginLifecycleProtocol
    from core.plugins.protocols_manager_dependencies import (
        PluginManagerDependenciesProtocol,
        PluginManagerPathsProtocol,
    )
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.runtime.request_context import RequestContext
    from core.state.compatibility import CompatibilityInfo
    from core.state.protocols import AuthoritativePluginStateTransitionReceipt
    from core.state.state_names import PluginRuntimeStateName
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict, JSONValue
    from core.types.protocols import HttpClientProtocol
    from plugins.manager.transfer_outcomes import ModelDownloadFinalization
    from plugins.worker.load_result import PluginWorkerLoadResult

__all__ = (
    "FetchLatestSoAIReleaseAsyncProtocol",
    "PluginDownloadManagerProtocol",
    "PluginManagerRuntimeProtocol",
    "RemoteSearchPluginProtocol",
)


class RemoteSearchPluginProtocol(Protocol):
    async def search_remote_models(
        self,
        query: str,
        *,
        limit: int = ...,
    ) -> Sequence[RemoteModelSearchResult | JSONDict]: ...


class FetchLatestSoAIReleaseAsyncProtocol(Protocol):
    async def __call__(
        self,
        http_client: httpx2.AsyncClient,
        *,
        timeout: float,
        module_dependencies: UpdaterModuleDependenciesProtocol,
        logger: LoggerProtocol | None = None,
        github_token: str | None = None,
    ) -> tuple[bool, JSONDict | None, str]: ...


class PluginWorkerControllerProtocol(Protocol):
    async def start(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def stop_plugin(self, plugin_name: str) -> None: ...

    async def delete_plugin_environment(self, plugin_name: str) -> None: ...

    async def update_runtime_flags(self, runtime_flags: RuntimeFlagsViewProtocol) -> None: ...

    async def load_plugin(
        self,
        *,
        plugin_name: str,
        plugin_package_root: str,
        plugin_entrypoint_path: str,
        plugin_file_hash: str,
        package_dependencies: list[str],
        plugin_config: JSONDict,
    ) -> PluginWorkerLoadResult: ...


class PluginManagerRuntimeProtocol(Protocol):
    state: PluginStateProtocol
    paths: PluginManagerPathsProtocol

    orchestrator_lifecycle: OrchestratorLifecycleProtocol | None
    policy: PluginManagerPolicy

    @property
    def dependencies(self) -> PluginManagerDependenciesProtocol: ...

    logger: LoggerProtocol
    worker_controller: PluginWorkerControllerProtocol

    @property
    def lifecycle(self) -> PluginLifecycleProtocol: ...

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def database_plugins(self) -> DatabasePluginsProtocol: ...

    @property
    def http_client(self) -> httpx2.AsyncClient | None: ...

    @property
    def uploads_enabled(self) -> bool: ...

    @property
    def downloads_enabled(self) -> bool: ...

    async def get_plugin_display_name(self, plugin_name: str) -> str: ...

    async def get_plugin_display_names(self, plugin_names: Iterable[str]) -> dict[str, str]: ...

    def normalize_plugin_name(self, plugin_name: str) -> str | None: ...

    async def get_plugin_instance(self, plugin_name: str) -> PluginInstanceProtocol | None: ...

    async def snapshot_clone_target_occupancy(
        self,
        source_plugin_name: str,
        source_instance: PluginInstanceProtocol | None,
        clone_models: bool,
    ) -> tuple[str, ...]: ...

    async def get_plugin_configuration(self, plugin_name: str) -> JSONDict: ...

    async def set_plugin_configuration(
        self,
        plugin_name: str,
        config_data: JSONDict,
        *,
        apply_runtime: bool = True,
    ) -> bool: ...

    async def refresh_plugin_runtime_configuration(
        self,
        plugin_name: str,
        *,
        auto_load: bool = True,
    ) -> JSONDict: ...

    async def get_backend_variants(self, plugin_name: str) -> JSONDict: ...

    async def save_backend_variant_selection(
        self,
        plugin_name: str,
        variant_id: JSONValue,
    ) -> JSONDict: ...

    async def snapshot_backend_variant_selection(
        self,
        plugin_name: str,
        requested_variant_id: JSONValue = None,
        *,
        has_requested_variant_id: bool = False,
    ) -> str: ...

    async def require_loaded_plugin(
        self,
        plugin_name: str,
        display_name: str | None = None,
        auto_load: bool = False,
        *,
        already_serialized: bool = False,
    ) -> PluginInstanceProtocol: ...

    async def require_ready(self) -> None: ...

    @property
    def initial_reconciliation_result(self) -> StartupPhaseResult: ...

    async def run_initial_reconciliation(self) -> None: ...

    def start_initial_reconciliation(self) -> None: ...

    async def wait_for_initial_reconciliation(self, timeout: float | None = None) -> bool: ...

    async def handle_cancel_task(self, command: Event) -> None: ...

    async def transition_plugin_manager_state(
        self,
        plugin_name: str,
        new_state: PluginRuntimeStateName,
        reason: str,
        context: RequestContext | None = None,
    ) -> AuthoritativePluginStateTransitionReceipt | None: ...

    def require_plugin_capability(
        self,
        instance: PluginInstanceProtocol,
        capability_name: str,
        failure_message: str,
    ) -> None: ...

    def require_online_mode(self, source: str) -> None: ...

    async def ensure_plugin_compatible(self, plugin_name: str) -> None: ...

    async def ensure_system_capabilities(
        self,
        plugin_name: str,
        action_description: str,
        action_key: str | None = None,
    ) -> JSONDict: ...

    async def reload_plugin_instance(self, plugin_name: str) -> None: ...

    async def release_discovery_plugin_instance(self, plugin_name: str) -> None: ...

    async def check_for_backend_updates(self) -> dict[str, JSONDict]: ...

    async def describe_model_variants(
        self,
        plugin_name: str,
        model_id: str,
        *,
        include_speed_tests: bool = False,
        hw_manager: HardwareManagerProtocol | None = None,
        http_client: HttpClientProtocol | None = None,
    ) -> list[JSONDict]: ...

    async def list_plugins(self) -> list[JSONDict]: ...

    async def search_remote_models(
        self,
        plugin_name: str,
        query: str,
        *,
        limit: int = 10,
    ) -> list[JSONDict]: ...

    async def register_model_download(self, plugin_name: str) -> None: ...

    async def finalize_model_download(
        self,
        plugin_name: str,
        *,
        context: RequestContext | None,
        discovery_requested: bool,
    ) -> ModelDownloadFinalization: ...

    async def download_plugin_package(
        self,
        url: str,
        context: RequestContext,
        http_client: HttpClientProtocol,
    ) -> PluginActionResponse: ...

    async def upload_staged_plugin_package(
        self,
        upload: PluginStagedUploadProtocol,
        context: RequestContext,
    ) -> PluginActionResponse: ...

    async def set_incompatibility_override(
        self,
        plugin_name: str,
        override: bool,
    ) -> CompatibilityInfo: ...
