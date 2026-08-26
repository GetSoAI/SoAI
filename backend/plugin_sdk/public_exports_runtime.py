"""SoAI - Plugin SDK lazy public export resolver [backend/plugin_sdk/public_exports_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from importlib import import_module

from plugin_sdk.protocols import LazyPluginSdkExportProtocol
from plugin_sdk.public_exports_data import LAZY_IMPORT_MODULES, PUBLIC_EXPORTS

__all__ = (
    "PLUGIN_SDK_PUBLIC_EXPORTS",
    "resolve_plugin_sdk_export",
    "list_plugin_sdk_exports",
)

PLUGIN_SDK_PUBLIC_EXPORTS = PUBLIC_EXPORTS


def _require_lazy_plugin_sdk_export(
    value: LazyPluginSdkExportProtocol,
) -> LazyPluginSdkExportProtocol:
    return value


def resolve_plugin_sdk_export(name: str) -> LazyPluginSdkExportProtocol:
    for module_path, symbol_names in LAZY_IMPORT_MODULES:
        if name in symbol_names:
            module = import_module(module_path)
            try:
                return _require_lazy_plugin_sdk_export(module.__dict__[name])
            except KeyError as exception:
                raise AttributeError(
                    f"module '{module_path}' has no attribute {name!r}",
                ) from exception
    raise AttributeError(f"module 'plugin_sdk' has no attribute {name!r}")


def list_plugin_sdk_exports() -> list[str]:
    return list(PUBLIC_EXPORTS)
