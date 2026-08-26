"""SoAI - Configuration services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/configuration/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.config.protocols import ConfigManagerProtocol, ConfigProtocol
    from core.files.protocols import FilesPathResolverProtocol
    from core.orchestrator.routing_config import RoutingConfig
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("ConfigurationServicesProtocol",)


class ConfigurationServicesProtocol(Protocol):
    @property
    def config(self) -> ConfigProtocol: ...

    @property
    def files(self) -> FilesPathResolverProtocol: ...

    @property
    def routing_config(self) -> RoutingConfig: ...

    @property
    def runtime_flags(self) -> RuntimeFlagsViewProtocol: ...

    @property
    def config_manager(self) -> ConfigManagerProtocol: ...
