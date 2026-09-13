"""SoAI - Plugin-related events and commands [backend/core/events/types_plugins.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from core.errors.error_types import ErrorType
from core.events.types_base import Event, ReplyableUserCommand, UserCommand
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from core.state.state_names import PluginRuntimeStateName

__all__ = (
    "AuthoritativeStateChangeEvent",
    "CircuitBreakerStateChangedEvent",
    "ClearQuarantineCommand",
    "ClonePluginCommand",
    "DeletePluginCommand",
    "DownloadPluginPackageCommand",
    "ErrorEvent",
    "ForceCleanupPluginCommand",
    "InstallPluginBackendCommand",
    "InstalledPluginsChangedEvent",
    "PluginInstallationStateChangedEvent",
    "PluginLoadedEvent",
    "PluginLastUsedChangedEvent",
    "PluginPurgedEvent",
    "PluginRuntimeStateChangedEvent",
    "PluginScopedEvent",
    "PluginStoppedEvent",
    "PluginUnloadedEvent",
    "ProviderStatusUpdatedEvent",
    "ProviderDiscoveryRequestedEvent",
    "PurgeModelsForPluginCommand",
    "RemovePluginBackendCommand",
    "RequestPluginDisableCommand",
    "RequestPluginEnableCommand",
    "RequestPluginStopAndWaitCommand",
    "StopAllPluginsCommand",
    "UpdateAllPluginBackendsCommand",
    "UpdatePluginBackendCommand",
    "UploadPluginCommand",
    "ValidateProviderCommand",
)


@dataclass(slots=True)
class ErrorEvent(Event):
    message: str
    context: RequestContext | None = None
    error_type: ErrorType = ErrorType.SERVER_ERROR


@dataclass(slots=True)
class PluginScopedEvent(Event):
    plugin_name: str

    @property
    def partition_plugin_name(self) -> str:
        return self.plugin_name


@dataclass(slots=True)
class PluginLoadedEvent(PluginScopedEvent): ...


@dataclass(slots=True)
class PluginStoppedEvent(PluginScopedEvent): ...


@dataclass(slots=True)
class PluginUnloadedEvent(PluginScopedEvent): ...


@dataclass(slots=True)
class PluginPurgedEvent(PluginScopedEvent): ...


@dataclass(slots=True)
class PluginLastUsedChangedEvent(PluginScopedEvent):
    last_used_at_ms: int
    revision: int


@dataclass(slots=True)
class RequestPluginStopAndWaitCommand(ReplyableUserCommand):
    plugin_name: str
    request_source: Literal["user", "model_deletion"] = "user"
    context: RequestContext | None = None


@dataclass(slots=True)
class InstallPluginBackendCommand(ReplyableUserCommand):
    plugin_name: str
    backend_variant_id: str | None = None
    context: RequestContext | None = None


@dataclass(slots=True)
class RemovePluginBackendCommand(ReplyableUserCommand):
    plugin_name: str
    delete_models: bool
    context: RequestContext | None = None


@dataclass(slots=True)
class UpdatePluginBackendCommand(ReplyableUserCommand):
    plugin_name: str
    backend_variant_id: str | None = None
    context: RequestContext | None = None


@dataclass(slots=True)
class ClonePluginCommand(ReplyableUserCommand):
    plugin_name: str
    clone_models: bool
    target_name: str | None = None
    field_overrides: JSONDict | None = None
    context: RequestContext | None = None


@dataclass(slots=True)
class UpdateAllPluginBackendsCommand(ReplyableUserCommand):
    plugin_name: str | None = None
    context: RequestContext | None = None


@dataclass(slots=True)
class StopAllPluginsCommand(UserCommand):
    initiator: Literal["shutdown", "user"] = "user"
    context: RequestContext | None = None


@dataclass(slots=True)
class ValidateProviderCommand(UserCommand):
    provider_id: str
    context: RequestContext | None = None


@dataclass(slots=True)
class InstalledPluginsChangedEvent(Event):
    installed_plugin_names: set[str]


@dataclass(slots=True)
class DownloadPluginPackageCommand(ReplyableUserCommand):
    url: str
    plugin_name: str | None = None
    context: RequestContext | None = None


@dataclass(slots=True)
class UploadPluginCommand(ReplyableUserCommand):
    temp_file_path: str
    original_filename: str
    plugin_name: str | None = None
    context: RequestContext | None = None


@dataclass(slots=True)
class DeletePluginCommand(ReplyableUserCommand):
    plugin_name: str
    delete_models: bool
    context: RequestContext | None = None


@dataclass(slots=True)
class ForceCleanupPluginCommand(ReplyableUserCommand):
    plugin_name: str
    context: RequestContext | None = None


@dataclass(slots=True)
class PurgeModelsForPluginCommand(UserCommand):
    plugin_name: str
    context: RequestContext | None = None


@dataclass(slots=True)
class RequestPluginDisableCommand(ReplyableUserCommand):
    plugin_name: str
    context: RequestContext | None = None


@dataclass(slots=True)
class RequestPluginEnableCommand(ReplyableUserCommand):
    plugin_name: str
    context: RequestContext | None = None


@dataclass(slots=True)
class ClearQuarantineCommand(ReplyableUserCommand):
    plugin_name: str
    context: RequestContext | None = None


@dataclass(slots=True)
class ProviderStatusUpdatedEvent(PluginScopedEvent):
    provider_id: str
    new_status: str
    error: str | None = None


@dataclass(slots=True)
class ProviderDiscoveryRequestedEvent(PluginScopedEvent):
    provider_id: str
    provider_revision: int


@dataclass(slots=True)
class AuthoritativeStateChangeEvent(PluginScopedEvent):
    publication_sequence: int = field(default=0, kw_only=True)
    previous_state: PluginRuntimeStateName
    new_state: PluginRuntimeStateName
    reason: str = ""
    context: RequestContext | None = None


@dataclass(slots=True)
class PluginInstallationStateChangedEvent(AuthoritativeStateChangeEvent):
    authority: Literal["PluginManager"] = "PluginManager"


@dataclass(slots=True)
class PluginRuntimeStateChangedEvent(AuthoritativeStateChangeEvent):
    authority: Literal["Orchestrator"] = "Orchestrator"
    details: JSONDict = field(default_factory=dict[str, JSONValue])


@dataclass(slots=True)
class CircuitBreakerStateChangedEvent(Event):
    plugin_name: str
    state: str
    failure_count: int
    last_failure_at_ms: int
    is_open: bool
    recovery_timeout_sec: int
    failure_window_sec: int
    failure_threshold: int
