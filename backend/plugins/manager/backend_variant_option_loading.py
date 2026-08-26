"""SoAI - Backend variant option loading for plugin manager flows [backend/plugins/manager/backend_variant_option_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.backend_variant_option_validation import (
    require_backend_variant_options,
)
from core.plugins.backend_variant_options import normalize_backend_variant_options
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = ("load_backend_variant_options",)


async def load_backend_variant_options(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> list[JSONDict]:
    plugin_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    if plugin_record is not None:
        options_value = plugin_record.get("backend_variant_options")
        if isinstance(options_value, str) and options_value.strip():
            parsed_options = parse_json_value(
                options_value,
                field="plugin backend_variant_options",
            )
            options = require_backend_variant_options(
                parsed_options,
                field_name="plugin backend_variant_options",
            )
            return normalize_backend_variant_options(options)
        if isinstance(options_value, list):
            options = require_backend_variant_options(
                options_value,
                field_name="plugin backend_variant_options",
            )
            return normalize_backend_variant_options(options)
    return normalize_backend_variant_options([])
