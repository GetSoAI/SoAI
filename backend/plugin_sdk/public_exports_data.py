"""SoAI - Plugin SDK public export data aggregation [backend/plugin_sdk/public_exports_data.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.sdk_public_all_exports import PUBLIC_PLUGIN_SDK_EXPORTS
from plugin_sdk.public_exports_lazy_data import LAZY_IMPORT_MODULES

PUBLIC_EXPORTS: tuple[str, ...] = PUBLIC_PLUGIN_SDK_EXPORTS

__all__ = (
    "LAZY_IMPORT_MODULES",
    "PUBLIC_EXPORTS",
)
