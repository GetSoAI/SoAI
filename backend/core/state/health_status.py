"""SoAI - Plugin health status types and constants [backend/core/state/health_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    type PluginHealthStatus = Literal[
        "ok",
        "recovering",
        "open",
        "quarantined",
        "disabled",
    ]
else:
    PluginHealthStatus = Literal[
        "ok",
        "recovering",
        "open",
        "quarantined",
        "disabled",
    ]

__all__ = ()

PLUGIN_HEALTH_RECOVERING: Final[str] = "recovering"
PLUGIN_HEALTH_OPEN: Final[str] = "open"
PLUGIN_HEALTH_QUARANTINED: Final[str] = "quarantined"
PLUGIN_HEALTH_DISABLED: Final[str] = "disabled"
