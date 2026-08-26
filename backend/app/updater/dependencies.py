"""SoAI - Updater service dependency containers [backend/app/updater/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationUpdaterModuleDependencies
from app.edition_composition import UpdaterComposition
from app.updater.errors import UpdaterArgs
from core.di.validation import require_dependencies
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from app.updater.internal_protocols import UpdaterApiClientProtocol
    from core.config.protocols import ConfigProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "PluginUpdateServiceDependencies",
    "SoftwareUpdateServiceDependencies",
    "UpdaterApiClientDependencies",
)


@dataclass(frozen=True, slots=True)
class UpdaterApiClientDependencies:
    logger: LoggerProtocol
    module_dependencies: ApplicationUpdaterModuleDependencies
    config: ConfigProtocol
    base_path: str
    args: UpdaterArgs
    edition: str

    def __post_init__(self) -> None:
        require_dependencies(
            owner="UpdaterApiClientDependencies",
            args=self.args,
            base_path=self.base_path,
            config=self.config,
            edition=self.edition,
            logger=self.logger,
            module_dependencies=self.module_dependencies,
        )


@dataclass(frozen=True, slots=True)
class PluginUpdateServiceDependencies:
    args: UpdaterArgs
    logger: LoggerProtocol
    api_client: UpdaterApiClientProtocol
    api_timeout: float
    stream_timeout: float

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginUpdateServiceDependencies",
            api_client=self.api_client,
            api_timeout=self.api_timeout,
            args=self.args,
            logger=self.logger,
            stream_timeout=self.stream_timeout,
        )


@dataclass(frozen=True, slots=True)
class SoftwareUpdateServiceDependencies:
    args: UpdaterArgs
    logger: LoggerProtocol
    api_client: UpdaterApiClientProtocol
    module_dependencies: ApplicationUpdaterModuleDependencies
    config: ConfigProtocol
    config_path: str
    base_path: str
    temp_path: str
    platform_name: str
    platform_id: str | None
    main_py_path: str | None
    local_version: str | None
    timeout: float
    api_timeout: float
    download_timeout: float
    storage_manager: StorageManagerProtocol
    updater: UpdaterComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SoftwareUpdateServiceDependencies",
            api_client=self.api_client,
            api_timeout=self.api_timeout,
            args=self.args,
            base_path=self.base_path,
            config=self.config,
            config_path=self.config_path,
            download_timeout=self.download_timeout,
            logger=self.logger,
            module_dependencies=self.module_dependencies,
            platform_name=self.platform_name,
            storage_manager=self.storage_manager,
            temp_path=self.temp_path,
            timeout=self.timeout,
            updater=self.updater,
        )
