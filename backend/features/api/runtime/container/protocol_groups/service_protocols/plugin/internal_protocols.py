"""SoAI - Plugin services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/plugin/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.plugins.protocols import PluginManagerProtocol
    from core.webui_manager.protocols import WebUIManagerProtocol

__all__ = ("PluginServicesProtocol",)


class PluginServicesProtocol(Protocol):
    @property
    def plugin_manager(self) -> PluginManagerProtocol: ...

    @property
    def webui_manager(self) -> WebUIManagerProtocol: ...
