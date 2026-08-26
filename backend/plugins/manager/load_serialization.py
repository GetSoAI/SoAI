"""SoAI - Plugin load serialization primitives [backend/plugins/manager/load_serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = ("serialized_plugin_load_scope",)


@asynccontextmanager
async def serialized_plugin_load_scope(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> AsyncGenerator[None]:
    async with self.dependencies.infrastructure.lifecycle.plugin_lock_scope(plugin_name):
        yield
