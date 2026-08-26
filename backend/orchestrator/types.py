"""SoAI - Orchestrator type definitions [backend/orchestrator/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
from core.di.validation import require_dependencies
from core.models.protocols_database import DatabaseModelsProtocol
from core.orchestrator.routing_config import RoutingConfig, RoutingConfigHolder
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from orchestrator.lifecycle.start_task_tracking import SchedulerStartTaskTracker

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.events.protocols import EventBusProtocol
    from core.licensing.protocols import LicensingStatusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelParameterServiceProtocol,
        ModelResolutionServiceProtocol,
        ParameterManagerProtocol,
        VirtualModelServiceProtocol,
    )
    from core.openai.token_counter import PromptTokenCounter
    from core.plugins.protocols import PluginManagerProtocol
    from core.state.protocols import (
        AuthoritativePluginStateTransitionsProtocol,
        StateAggregatorProtocol,
    )

__all__ = ("OrchestratorDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorDependencies:
    config: ConfigProtocol
    bus: EventBusProtocol
    model_resolution_service: ModelResolutionServiceProtocol
    model_information_service: ModelInformationServiceProtocol
    model_parameter_service: ModelParameterServiceProtocol
    model_virtual_model_service: VirtualModelServiceProtocol
    param_manager: ParameterManagerProtocol
    database_models: DatabaseModelsProtocol
    database_plugins: DatabasePluginsProtocol
    database_api_keys: DatabaseAPIKeysProtocol
    model_services_ready_event: asyncio.Event
    plugin_manager: PluginManagerProtocol
    routing_config: RoutingConfig
    routing_config_holder: RoutingConfigHolder
    metrics: MetricsManagerProtocol
    state_aggregator: StateAggregatorProtocol
    authoritative_plugin_state_transitions: AuthoritativePluginStateTransitionsProtocol
    audit_logger: LoggerProtocol
    cancellation_coordinator: CancellationCoordinatorProtocol
    cancellation_history: CancellationHistoryProtocol
    scheduler_start_task_tracker: SchedulerStartTaskTracker
    task_cancellation_binder: TaskCancellationBinderProtocol
    task_finalizer_tracker: TaskFinalizerTrackerProtocol
    prompt_token_counter: PromptTokenCounter
    licensing_status: LicensingStatusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorDependencies",
            audit_logger=self.audit_logger,
            bus=self.bus,
            config=self.config,
            cancellation_coordinator=self.cancellation_coordinator,
            cancellation_history=self.cancellation_history,
            database_api_keys=self.database_api_keys,
            database_models=self.database_models,
            database_plugins=self.database_plugins,
            licensing_status=self.licensing_status,
            metrics=self.metrics,
            model_information_service=self.model_information_service,
            model_parameter_service=self.model_parameter_service,
            model_resolution_service=self.model_resolution_service,
            model_services_ready_event=self.model_services_ready_event,
            model_virtual_model_service=self.model_virtual_model_service,
            param_manager=self.param_manager,
            plugin_manager=self.plugin_manager,
            prompt_token_counter=self.prompt_token_counter,
            routing_config=self.routing_config,
            routing_config_holder=self.routing_config_holder,
            scheduler_start_task_tracker=self.scheduler_start_task_tracker,
            state_aggregator=self.state_aggregator,
            authoritative_plugin_state_transitions=self.authoritative_plugin_state_transitions,
            task_cancellation_binder=self.task_cancellation_binder,
            task_finalizer_tracker=self.task_finalizer_tracker,
        )
