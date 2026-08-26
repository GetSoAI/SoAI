"""SoAI - App internal protocols [backend/app/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import socket
from collections.abc import Collection, Sequence
from typing import TYPE_CHECKING, Protocol

from core.app.protocols import ApplicationRuntimeCoordinatorProtocol
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.metrics.protocols import MetricsManagerProtocol

if TYPE_CHECKING:
    from uvicorn.config import Config

    from app.updater.release_manifest_types import ReleaseManifestV1
    from core.app.protocols import ApplicationUpdateOutcome
    from core.licensing.types import Edition
    from core.logging.protocols import LoggerProtocol
    from core.meta.instance_identity import InstanceIdentity
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONObject

__all__ = (
    "ApplicationConfigReloadHandlerProtocol",
    "ApplicationHostServiceProtocol",
    "ApplicationRuntimeCoordinatorViewProtocol",
    "ApplicationUpdateServiceProtocol",
    "BannerSystemProtocol",
    "CloseableServerProtocol",
    "DiscoveryServerProtocol",
    "InstanceLockProtocol",
    "HostPersistenceProtocol",
    "LifecycleActorProtocol",
    "LifecycleCoordinatorProtocol",
    "LogBannerSystemProtocol",
    "MetricsAwareDatabaseCoreProtocol",
    "MetricsAwareEventBusProtocol",
    "StagedUpdateValidationProtocol",
    "UpdateStatusBuilderProtocol",
    "UvicornConnectionProtocol",
    "UvicornServerStateProtocol",
    "UvicornServerProtocol",
)


class HostPersistenceProtocol(Protocol):
    def __call__(
        self,
        *,
        runtime_flags: RuntimeFlagsViewProtocol,
        base_dir: str,
        command_executor: CommandExecutorProtocol | None,
        logger: LoggerProtocol,
    ) -> None: ...


class StagedUpdateValidationProtocol(Protocol):
    def __call__(self, staged_root: str, manifest: ReleaseManifestV1) -> None: ...


class InstanceLockProtocol(Protocol):
    @property
    def lock_file(self) -> str: ...

    def release(self) -> None: ...


class LifecycleActorProtocol(Protocol): ...


class LifecycleCoordinatorProtocol(Protocol):
    def register_actor(self, actor: LifecycleActorProtocol) -> None: ...

    def actor_count(self) -> int: ...

    def register_server(self, server: UvicornServerProtocol, task: asyncio.Task[None]) -> None: ...

    def has_servers(self) -> bool: ...

    def server_count(self) -> int: ...

    async def shutdown_servers(self, timeout: float) -> None: ...

    async def wait_until_started(self, timeout: float) -> None: ...

    def require_servers_serving(self) -> None: ...


class DiscoveryServerProtocol(Protocol):
    async def start(
        self,
        host: str,
        main_api_port: int,
        scheme: str = "http",
        *,
        preferred_api_port: int,
        instance_identity: InstanceIdentity,
        edition: Edition,
        transport_layer_security_options: dict[str, str | int] | None = None,
    ) -> bool: ...

    def has_active_server(self) -> bool: ...

    async def stop(self) -> None: ...


class UpdateStatusBuilderProtocol(Protocol):
    def __call__(
        self,
        raw_current_version: str | None,
        release_info: JSONObject,
    ) -> JSONDict: ...


class BannerSystemProtocol(Protocol):
    def has_banner(self, key: str) -> bool: ...

    def register(self, key: str, *, color: str, message: str, level: int) -> None: ...


class CloseableServerProtocol(Protocol):
    def is_serving(self) -> bool: ...

    def close(self) -> None: ...

    async def wait_closed(self) -> None: ...


class UvicornConnectionProtocol(Protocol):
    transport: asyncio.Transport


class UvicornServerStateProtocol(Protocol):
    @property
    def connections(self) -> Collection[UvicornConnectionProtocol]: ...


class UvicornServerProtocol(Protocol):
    should_exit: bool
    force_exit: bool
    started: bool

    @property
    def servers(self) -> Sequence[CloseableServerProtocol] | None: ...

    @property
    def server_state(self) -> UvicornServerStateProtocol: ...

    async def serve(self, sockets: list[socket.socket] | None = None) -> None: ...

    async def shutdown(self) -> None: ...


class UvicornServerFactoryProtocol(Protocol):
    def __call__(self, configuration: Config, /) -> UvicornServerProtocol: ...


class LogBannerSystemProtocol(Protocol):
    def emit(self, key: str) -> None: ...

    def has_banner(self, key: str) -> bool: ...

    def register(self, *, key: str, color: str, message: str, level: int) -> None: ...


class MetricsAwareEventBusProtocol(EventBusProtocol, Protocol):
    def set_metrics_recorder(self, recorder: MetricsManagerProtocol | None) -> None: ...


class MetricsAwareDatabaseCoreProtocol(Protocol):
    def set_metrics_recorder(self, recorder: MetricsManagerProtocol | None) -> None: ...


class ApplicationConfigReloadHandlerProtocol(Protocol):
    async def handle_core_configuration_reload_event(self, event: Event) -> None: ...


class ApplicationRuntimeCoordinatorViewProtocol(ApplicationRuntimeCoordinatorProtocol, Protocol):
    @property
    def event_bus(self) -> EventBusProtocol | None: ...

    @property
    def config_reload_handler(self) -> ApplicationConfigReloadHandlerProtocol: ...


class ApplicationHostServiceProtocol(Protocol):
    async def shutdown_servers(self, timeout_sec: float) -> None: ...

    async def stop_discovery_server(self) -> None: ...


class ApplicationUpdateServiceProtocol(Protocol):
    async def update(self) -> tuple[ApplicationUpdateOutcome, str]: ...
