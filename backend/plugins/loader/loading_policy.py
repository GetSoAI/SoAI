"""SoAI - Plugin load persistence and publication policy [backend/plugins/loader/loading_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.state.state_names import PluginRuntimeStateName
    from core.types.json import JSONDict

__all__ = (
    "PluginLoadOutcome",
    "PluginLoadPolicy",
)


@dataclass(frozen=True, slots=True)
class PluginLoadPolicy:
    catalog_state: str | None
    announce: bool
    publish_failure_state: bool


@dataclass(frozen=True, slots=True)
class PluginLoadOutcome:
    instance: PluginInstanceProtocol
    plugin_data: JSONDict
    previous_state: PluginRuntimeStateName
    initial_state: PluginRuntimeStateName
    reason: str
    welcome_message: str | None
