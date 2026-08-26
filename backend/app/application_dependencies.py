"""SoAI - Application dependency bundles and runtime values [backend/app/application_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING

from app.internal_protocols import (
    BannerSystemProtocol,
    UpdateStatusBuilderProtocol,
    UvicornServerFactoryProtocol,
)
from core.di.validation import require_dependencies
from core.events.types_system import SystemRestartRequiredEvent
from core.logging.protocols import LoggerProtocol
from core.tasks.protocols import SpawnTrackedTaskCallable

if TYPE_CHECKING:
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    from core.config.protocols import ConfigProtocol
    from core.config.runtime_config import Config
    from core.events.types_system import SoAIMainState
    from core.logging.protocols import LogBannerSystemProtocol
    from features.api.runtime.container.auth_config import AuthConfig

__all__ = (
    "ApplicationBootstrapModuleDependencies",
    "ApplicationEnvironment",
    "ApplicationLifecycleModuleDependencies",
    "ApplicationLifecycleModuleView",
    "ApplicationLogging",
    "ApplicationMetadata",
    "ApplicationModuleDependencies",
    "ApplicationPaths",
    "ApplicationRuntimeModuleDependencies",
    "ApplicationSecurity",
    "ApplicationServerModuleDependencies",
    "ApplicationStartupModuleDependencies",
    "ApplicationUpdaterModuleDependencies",
    "EventTypesBundle",
)


@dataclass(slots=True, frozen=True)
class ApplicationMetadata:
    version: str


@dataclass(slots=True, frozen=True)
class ApplicationEnvironment:
    base_dir: str
    config_path: str
    main_venv_dir: str
    version: str


@dataclass(slots=True, frozen=True)
class ApplicationPaths:
    base_dir: str
    main_venv_dir: str
    config_path: str
    plugin_directory: str
    backends_directory: str
    pid_file_path: str


@dataclass(slots=True, frozen=True)
class ApplicationLogging:
    logger: LoggerProtocol
    bootstrap_logger: LoggerProtocol
    lifecycle_logger: LoggerProtocol
    gui_status: Callable[[str], None]
    banner_system: LogBannerSystemProtocol | None


@dataclass(slots=True, frozen=True)
class EventTypesBundle:
    system_restart_required_event: type[SystemRestartRequiredEvent]
    soai_main_state: type[SoAIMainState]


@dataclass(slots=True, frozen=True)
class ApplicationSecurity:
    fernet: tuple[Fernet, ...]
    primary_signing_secret: str
    verification_secrets: tuple[str, ...]
    auth_config: AuthConfig


@dataclass(slots=True, frozen=True)
class ApplicationLifecycleModuleView:
    banner_width: int
    register_banner_defaults: Callable[
        [BannerSystemProtocol, list[tuple[str, str, str, int]]],
        None,
    ]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationLifecycleModuleView",
            banner_width=self.banner_width,
            register_banner_defaults=self.register_banner_defaults,
        )


@dataclass(slots=True, frozen=True)
class ApplicationRuntimeModuleDependencies:
    application_lifecycle: ApplicationLifecycleModuleView
    event_types: EventTypesBundle
    log_banner_system_factory: Callable[[LoggerProtocol, int], LogBannerSystemProtocol]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationRuntimeModuleDependencies",
            application_lifecycle=self.application_lifecycle,
            event_types=self.event_types,
            log_banner_system_factory=self.log_banner_system_factory,
        )


@dataclass(slots=True, frozen=True)
class ApplicationServerModuleDependencies:
    api_initialize: Callable[[], FastAPI]
    prepare_tls_configuration: Callable[[ConfigProtocol], tuple[dict[str, str | int], bool]]
    spawn_tracked_task: SpawnTrackedTaskCallable
    uvicorn: ModuleType
    uvicorn_server_factory: UvicornServerFactoryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationServerModuleDependencies",
            api_initialize=self.api_initialize,
            prepare_tls_configuration=self.prepare_tls_configuration,
            spawn_tracked_task=self.spawn_tracked_task,
            uvicorn=self.uvicorn,
            uvicorn_server_factory=self.uvicorn_server_factory,
        )


@dataclass(slots=True, frozen=True)
class ApplicationStartupModuleDependencies:
    event_types: EventTypesBundle
    is_bind_all_interfaces_host: Callable[[str | None], bool]
    resolve_speed_test_path: Callable[[str], str | None]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationStartupModuleDependencies",
            event_types=self.event_types,
            is_bind_all_interfaces_host=self.is_bind_all_interfaces_host,
            resolve_speed_test_path=self.resolve_speed_test_path,
        )


@dataclass(slots=True, frozen=True)
class ApplicationLifecycleModuleDependencies:
    log_banner_system_factory: Callable[[LoggerProtocol, int], LogBannerSystemProtocol]
    banner_width: int = 70
    register_banner_defaults: Callable[
        [BannerSystemProtocol, list[tuple[str, str, str, int]]],
        None,
    ] = lambda _banner_system, _defaults: None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationLifecycleModuleDependencies",
            banner_width=self.banner_width,
            register_banner_defaults=self.register_banner_defaults,
            log_banner_system_factory=self.log_banner_system_factory,
        )


@dataclass(slots=True, frozen=True)
class ApplicationBootstrapModuleDependencies:
    coerce_positive_int: Callable[..., int]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationBootstrapModuleDependencies",
            coerce_positive_int=self.coerce_positive_int,
        )


@dataclass(slots=True, frozen=True)
class ApplicationUpdaterModuleDependencies:
    httpx2: ModuleType
    config_factory: type[Config]
    coerce_bool_with_default: Callable[..., bool]
    coerce_positive_float: Callable[..., float]
    build_update_status: UpdateStatusBuilderProtocol
    normalize_version_string: Callable[[str], str]
    yaml: ModuleType

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationUpdaterModuleDependencies",
            build_update_status=self.build_update_status,
            config_factory=self.config_factory,
            coerce_bool_with_default=self.coerce_bool_with_default,
            coerce_positive_float=self.coerce_positive_float,
            httpx2=self.httpx2,
            normalize_version_string=self.normalize_version_string,
            yaml=self.yaml,
        )


@dataclass(slots=True, frozen=True)
class ApplicationModuleDependencies:
    runtime: ApplicationRuntimeModuleDependencies
    server: ApplicationServerModuleDependencies
    startup: ApplicationStartupModuleDependencies
    lifecycle: ApplicationLifecycleModuleDependencies
    bootstrap: ApplicationBootstrapModuleDependencies
    updater: ApplicationUpdaterModuleDependencies

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationModuleDependencies",
            bootstrap=self.bootstrap,
            lifecycle=self.lifecycle,
            runtime=self.runtime,
            server=self.server,
            startup=self.startup,
            updater=self.updater,
        )
