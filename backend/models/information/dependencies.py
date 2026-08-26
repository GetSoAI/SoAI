"""SoAI - Model information service dependencies [backend/models/information/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.models.protocols import (
    ModelRegistryProtocol,
    ParameterManagerProtocol,
)
from core.models.protocols_database import DatabaseModelsProtocol
from core.orchestrator.routing_config import RoutingConfigHolder
from core.plugins.protocols import PluginManagerProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.state.protocols import StateAggregatorProtocol

__all__ = ("ModelInformationServiceDependencies",)


@dataclass(frozen=True, slots=True)
class ModelInformationServiceDependencies:
    database_models: DatabaseModelsProtocol
    database_plugins: DatabasePluginsProtocol
    plugin_manager: PluginManagerProtocol
    state_aggregator: StateAggregatorProtocol
    model_registry: ModelRegistryProtocol
    param_manager: ParameterManagerProtocol
    routing_config_holder: RoutingConfigHolder
    installed_plugin_names_ref: Callable[[], set[str]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelInformationServiceDependencies",
            database_models=self.database_models,
            database_plugins=self.database_plugins,
            installed_plugin_names_ref=self.installed_plugin_names_ref,
            model_registry=self.model_registry,
            param_manager=self.param_manager,
            plugin_manager=self.plugin_manager,
            routing_config_holder=self.routing_config_holder,
            state_aggregator=self.state_aggregator,
        )
