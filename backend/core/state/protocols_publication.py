"""SoAI - Core state publication side-effect protocols [backend/core/state/protocols_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.events.types_plugins import (
        PluginInstallationStateChangedEvent,
        PluginRuntimeStateChangedEvent,
    )

__all__ = ("RuntimeStatePublicationSideEffectsProtocol",)


class RuntimeStatePublicationSideEffectsProtocol(Protocol):
    async def apply_local_publication(self, event: PluginRuntimeStateChangedEvent) -> None: ...

    async def apply_replayed_publication(
        self,
        event: PluginRuntimeStateChangedEvent | PluginInstallationStateChangedEvent,
    ) -> None: ...
