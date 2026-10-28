"""SoAI - Bounded model discovery provider phase coordination [backend/models/discovery/provider_bounded_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.plugins.protocols_instance import PluginInstanceProtocol
from core.types.json import JSONDict

__all__ = (
    "DISCOVERY_CONCURRENCY_LIMIT",
    "PRE_CHECK_CONCURRENCY_LIMIT",
    "DiscoveryPassCoordination",
    "PluginCheckFailure",
    "PluginCheckSuccess",
    "PluginCheckUnchanged",
    "ProviderCatalogDiscovery",
)

PRE_CHECK_CONCURRENCY_LIMIT = 5
DISCOVERY_CONCURRENCY_LIMIT = 5


@dataclass(frozen=True, slots=True)
class PluginCheckSuccess:
    plugin_name: str
    instance: PluginInstanceProtocol
    loaded_for_discovery: bool
    provider_catalog_only: bool = False


@dataclass(frozen=True, slots=True)
class PluginCheckFailure:
    plugin_name: str
    error: Exception


@dataclass(frozen=True, slots=True)
class PluginCheckUnchanged:
    plugin_name: str


@dataclass(frozen=True, slots=True)
class ProviderCatalogDiscovery:
    models: dict[str, JSONDict]


if TYPE_CHECKING:
    type PluginDiscoveryResult = dict[
        str, JSONDict
    ] | ProviderCatalogDiscovery | Exception | PluginCheckUnchanged | None


@dataclass(slots=True)
class DiscoveryPassCoordination:
    pending_prechecks: int
    precheck_permits: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(PRE_CHECK_CONCURRENCY_LIMIT),
    )
    provider_permits: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(DISCOVERY_CONCURRENCY_LIMIT),
    )
    prechecks_settled: asyncio.Event = field(default_factory=asyncio.Event)
    provider_phase_open: asyncio.Event = field(default_factory=asyncio.Event)
    existing_models: dict[str, dict[str, JSONDict]] = field(
        default_factory=dict[str, dict[str, JSONDict]],
    )

    def __post_init__(self) -> None:
        if self.pending_prechecks <= 0:
            self.prechecks_settled.set()

    def settle_precheck(self) -> None:
        self.pending_prechecks -= 1
        if self.pending_prechecks <= 0:
            self.prechecks_settled.set()

    def open_provider_phase(self, existing_models: dict[str, dict[str, JSONDict]]) -> None:
        self.existing_models = existing_models
        self.provider_phase_open.set()
