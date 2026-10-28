"""SoAI - Plugin state publishing helpers [backend/plugins/state/publishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.plugins.protocols_database import DatabasePluginsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("require_plugin_record",)


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
