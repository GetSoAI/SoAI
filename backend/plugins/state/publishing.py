"""SoAI - Plugin state publishing helpers [backend/plugins/state/publishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import NotFoundError, ValidationError
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.plugins.protocols_instance import PluginInstanceProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "require_plugin_instance",
    "require_plugin_record",
)


async def require_plugin_record(
    database_plugins: DatabasePluginsProtocol,
    plugin_name: str,
    *,
    error_cls: type[Exception] = ValidationError,
    message: str | None = None,
) -> JSONDict:
    record = await database_plugins.get_plugin_by_name(plugin_name)
    if not record:
        raise error_cls(message or f"Plugin '{plugin_name}' does not exist.")
    return record


async def require_plugin_instance(
    get_instance_fn: Callable[[str], Awaitable[PluginInstanceProtocol | None]],
    plugin_name: str,
    *,
    error_cls: type[Exception] = NotFoundError,
    message: str | None = None,
) -> PluginInstanceProtocol:
    instance = await get_instance_fn(plugin_name)
    if not instance:
        raise error_cls(message or f"Plugin '{plugin_name}' is not loaded.")
    return instance
