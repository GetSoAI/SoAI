"""SoAI - Proxy plugin instance dependencies [backend/plugins/worker/proxy_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from plugins.worker.internal_protocols import DownloadReservationScopeFactoryProtocol

if TYPE_CHECKING:
    from core.ipc.multiplexed import MultiplexedIpcServer
    from plugins.worker.surface import PluginRuntimeSurface

__all__ = ("ProxyPluginInstanceDependencies",)


@dataclass(frozen=True, slots=True)
class ProxyPluginInstanceDependencies:
    plugin_name: str
    worker_id: int
    server: MultiplexedIpcServer
    surface: PluginRuntimeSurface
    install_path: str
    download_reservation_scope_factory: DownloadReservationScopeFactoryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ProxyPluginInstanceDependencies",
            install_path=self.install_path,
            plugin_name=self.plugin_name,
            server=self.server,
            surface=self.surface,
            worker_id=self.worker_id,
            download_reservation_scope_factory=self.download_reservation_scope_factory,
        )
