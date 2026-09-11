"""SoAI - Plugin manager protocol contracts for cross-subsystem interfaces [backend/core/plugins/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, Protocol

__all__ = (
    "OpenAICapabilityPluginClassProtocol",
    "PluginManagerProtocol",
)


if TYPE_CHECKING:
    from collections.abc import Iterable

    from core.hardware.protocols import HardwareManagerProtocol
    from core.orchestrator.protocols_lifecycle import OrchestratorLifecycleProtocol
    from core.plugins.logo_contract import PluginLogoResult
    from core.plugins.protocols_instance import (
        PluginActionResponseProtocol,
        PluginInstanceProtocol,
        PluginStagedUploadProtocol,
    )
    from core.plugins.protocols_lifecycle import PluginLifecycleProtocol
    from core.plugins.protocols_manager_dependencies import (
        PluginManagerDependenciesProtocol,
        PluginManagerPathsProtocol,
        PluginManagerStateProtocol,
        PluginUpdaterProtocol,
    )
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.runtime.request_context import RequestContext
    from core.runtime.startup_status import StartupPhaseResult
    from core.state.compatibility import CompatibilityInfo
    from core.types.json import JSONDict
    from core.types.json_value import JSONValue
    from core.types.protocols import HttpClientProtocol


class OpenAICapabilityPluginClassProtocol(Protocol):
    SUPPORTS_CHAT_COMPLETIONS: ClassVar[bool]
    SUPPORTS_COMPLETIONS: ClassVar[bool]
    SUPPORTS_RESPONSES: ClassVar[bool]
    SUPPORTS_EMBEDDINGS: ClassVar[bool]
    SUPPORTS_IMAGES: ClassVar[bool]
    SUPPORTS_IMAGE_EDITS: ClassVar[bool]
    SUPPORTS_IMAGE_VARIATIONS: ClassVar[bool]
    SUPPORTS_AUDIO_TRANSCRIPTIONS: ClassVar[bool]
    SUPPORTS_AUDIO_TRANSLATIONS: ClassVar[bool]
    SUPPORTS_AUDIO_SPEECH: ClassVar[bool]
    SUPPORTS_VISION: ClassVar[bool]
    SUPPORTS_INPUT_AUDIO: ClassVar[bool]
    SUPPORTS_TOOL_CALLING: ClassVar[bool]
    SUPPORTS_PARALLEL_TOOL_CALLS: ClassVar[bool]
    SUPPORTS_STRUCTURED_OUTPUT: ClassVar[bool]
    SUPPORTS_JSON_SCHEMA: ClassVar[bool]
    SUPPORTS_RESPONSES_RETRIEVE: ClassVar[bool]
    SUPPORTS_RESPONSES_DELETE: ClassVar[bool]
    SUPPORTS_RESPONSES_CANCEL: ClassVar[bool]
    SUPPORTS_RESPONSES_INPUT_ITEMS: ClassVar[bool]
    SUPPORTS_RESPONSES_INPUT_TOKENS: ClassVar[bool]
    SUPPORTED_MODALITIES: ClassVar[Sequence[str]]


class PluginManagerProtocol(Protocol):
    async def prepare_logo(
        self, plugin_name: str, archive_hash: str
    ) -> PluginLogoResult | None: ...
    @property
    def state(self) -> PluginManagerStateProtocol: ...
    @property
    def paths(self) -> PluginManagerPathsProtocol: ...
    @property
    def dependencies(self) -> PluginManagerDependenciesProtocol: ...
    @property
    def lifecycle(self) -> PluginLifecycleProtocol: ...
    @property
    def updater(self) -> PluginUpdaterProtocol: ...
    @property
    def uploads_enabled(self) -> bool: ...
    @property
    def downloads_enabled(self) -> bool: ...
    async def initialize(self) -> None: ...
    async def require_ready(self) -> None: ...
    @property
    def initial_reconciliation_result(self) -> StartupPhaseResult: ...
    async def run_initial_reconciliation(self) -> None: ...
    def start_initial_reconciliation(self) -> None: ...
    async def reload_plugin_instance(self, plugin_name: str) -> None: ...
    async def wait_for_initial_reconciliation(self, timeout: float | None = None) -> bool: ...
    async def perform_startup_recovery_stop_sweep(self) -> None: ...
    async def list_plugins(self) -> list[JSONDict]: ...
    async def get_plugin_display_names(self, plugin_names: Iterable[str]) -> dict[str, str]: ...
    async def get_plugin_display_name(self, plugin_name: str) -> str: ...
    async def is_clone_integrity_quarantined(self, plugin_name: str) -> bool: ...
    def is_known_plugin(self, plugin_name: str) -> bool: ...
    def normalize_plugin_name(self, plugin_name: str) -> str | None: ...
    async def get_plugin_instance(self, plugin_name: str) -> PluginInstanceProtocol | None: ...
    async def snapshot_clone_target_occupancy(
        self,
        source_plugin_name: str,
        source_instance: PluginInstanceProtocol | None,
        clone_models: bool,
    ) -> tuple[str, ...]: ...
    async def get_plugin_configuration(self, plugin_name: str) -> JSONDict: ...
    async def set_plugin_configuration(self, plugin_name: str, config_data: JSONDict) -> bool: ...
    async def update_runtime_flags(self, runtime_flags: RuntimeFlagsViewProtocol) -> None: ...
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
    async def is_model_download_in_progress(self, plugin_name: str) -> bool: ...
    async def mark_discovery_pending_after_download(self, plugin_name: str) -> None: ...
    async def describe_model_variants(
        self,
        plugin_name: str,
        model_id: str,
        *,
        include_speed_tests: bool = False,
        hw_manager: HardwareManagerProtocol | None = None,
        http_client: HttpClientProtocol | None = None,
    ) -> list[JSONDict]: ...
    async def search_remote_models(
        self,
        plugin_name: str,
        query: str,
        *,
        limit: int = 10,
    ) -> list[JSONDict]: ...
    async def check_for_backend_updates(self) -> dict[str, JSONDict]: ...
    def bind_orchestrator_lifecycle(
        self,
        orchestrator_lifecycle: OrchestratorLifecycleProtocol,
    ) -> None: ...
    async def begin_shutdown(self) -> None: ...
    async def finalize_shutdown(self) -> None: ...
    async def shutdown(self) -> None: ...
    async def ensure_plugin_compatible(self, plugin_name: str) -> None: ...
    async def ensure_plugin_capability(
        self,
        plugin_name: str,
        capability_name: str,
        action_description: str,
    ) -> None: ...
    async def ensure_system_capabilities(
        self,
        plugin_name: str,
        action_description: str,
        action_key: str | None = None,
    ) -> JSONDict: ...
    async def download_plugin_package(
        self,
        url: str,
        context: RequestContext,
        http_client: HttpClientProtocol,
    ) -> PluginActionResponseProtocol: ...
    async def upload_staged_plugin_package(
        self,
        upload: PluginStagedUploadProtocol,
        context: RequestContext,
    ) -> PluginActionResponseProtocol: ...
    async def set_incompatibility_override(
        self,
        plugin_name: str,
        override: bool,
    ) -> CompatibilityInfo: ...
    async def require_loaded_plugin(
        self,
        plugin_name: str,
        display_name: str | None = None,
        auto_load: bool = False,
        *,
        already_serialized: bool = False,
    ) -> PluginInstanceProtocol: ...
    async def release_discovery_plugin_instance(self, plugin_name: str) -> None: ...
