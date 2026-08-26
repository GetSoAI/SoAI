"""SoAI - Plugin SDK public API surface and exports [backend/plugin_sdk/__init__.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from plugin_sdk.protocols import LazyPluginSdkExportProtocol
from plugin_sdk.public_exports_runtime import (
    PLUGIN_SDK_PUBLIC_EXPORTS,
    list_plugin_sdk_exports,
    resolve_plugin_sdk_export,
)

__all__ = ("PLUGIN_SDK_PUBLIC_EXPORTS",)


def __getattr__(name: str) -> LazyPluginSdkExportProtocol:
    value = resolve_plugin_sdk_export(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return list_plugin_sdk_exports()
