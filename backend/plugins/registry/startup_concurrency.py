"""SoAI - Plugin startup concurrency resolution [backend/plugins/registry/startup_concurrency.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_int

if TYPE_CHECKING:
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("resolve_plugin_startup_concurrency",)

STARTUP_CONCURRENCY_CONFIG_KEY = "PLUGINS.PERFORMANCE.STARTUP_CONCURRENCY"


def resolve_plugin_startup_concurrency(manager: PluginManagerRuntimeProtocol) -> int:
    concurrency_value = manager.dependencies.core.config.get(
        STARTUP_CONCURRENCY_CONFIG_KEY,
        10,
    )
    return coerce_positive_int(
        concurrency_value,
        default=10,
        minimum=1,
        label=STARTUP_CONCURRENCY_CONFIG_KEY,
    )
