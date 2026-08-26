"""SoAI - Orchestrator lifecycle service composition wiring [backend/orchestrator/lifecycle/service_wiring.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.orchestrator.protocols_lifecycle import (
    OrchestratorCircuitBreakersProtocol,
    OrchestratorLifecyclePublisherProtocol,
)
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.lifecycle.circuit_breaker_dependencies import (
    OrchestratorLifecycleCircuitBreakersDependencies,
)
from orchestrator.lifecycle.circuit_breakers import OrchestratorLifecycleCircuitBreakers
from orchestrator.lifecycle.dependencies import OrchestratorLifecycleDependencies
from orchestrator.lifecycle.recovery import (
    OrchestratorLifecycleRecovery,
    OrchestratorLifecycleRecoveryDependencies,
)
from orchestrator.lifecycle.routing_config import (
    OrchestratorLifecycleRoutingConfig,
    OrchestratorLifecycleRoutingConfigDependencies,
)
from orchestrator.lifecycle.runtime_mutations import (
    OrchestratorLifecycleRuntimeMutations,
    OrchestratorLifecycleRuntimeMutationsDependencies,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleRecoveryProtocol,
    OrchestratorLifecycleRoutingConfigProtocol,
    OrchestratorLifecycleRuntimeMutationsProtocol,
    OrchestratorLifecycleShutdownCoordinatorProtocol,
    OrchestratorLifecycleStartupProtocol,
    OrchestratorLifecycleTaskTrackingProtocol,
    OrchestratorLifecycleUserCommandsProtocol,
    OrchestratorLifecycleWatchersProtocol,
)
from orchestrator.lifecycle.shutdown import (
    OrchestratorLifecycleShutdown,
    OrchestratorLifecycleShutdownDependencies,
)
from orchestrator.lifecycle.startup import (
    OrchestratorLifecycleStartup,
    OrchestratorLifecycleStartupDependencies,
)
from orchestrator.lifecycle.state_access.internal_protocols import (
    RoutingConfigProviderProtocol,
)
from orchestrator.lifecycle.state_change_side_effects import (
    RuntimeStateSideEffects,
    RuntimeStateSideEffectsDependencies,
)
from orchestrator.lifecycle.task_tracking.dependencies import TaskTrackingDependencies
from orchestrator.lifecycle.task_tracking.service import (
    OrchestratorLifecycleTaskTracking,
)
from orchestrator.lifecycle.user_commands.dependencies import (
    OrchestratorLifecycleUserCommandsDependencies,
)
from orchestrator.lifecycle.user_commands.service import (
    OrchestratorLifecycleUserCommands,
)
from orchestrator.lifecycle.watchers import OrchestratorLifecycleWatchers
from orchestrator.lifecycle.watchers_dependencies import (
    OrchestratorLifecycleWatchersDependencies,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "LifecycleServiceBundle",
    "build_lifecycle_service_bundle",
)


@dataclass(frozen=True, slots=True)
class LifecycleServiceBundle:
    routing: OrchestratorLifecycleRoutingConfigProtocol
    circuit_breakers: OrchestratorCircuitBreakersProtocol
    watchers: OrchestratorLifecycleWatchersProtocol
    publisher: OrchestratorLifecyclePublisherProtocol
    shutdown: OrchestratorLifecycleShutdownCoordinatorProtocol
    task_tracking: OrchestratorLifecycleTaskTrackingProtocol
    startup: OrchestratorLifecycleStartupProtocol
    user_commands: OrchestratorLifecycleUserCommandsProtocol
    recovery: OrchestratorLifecycleRecoveryProtocol
    runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol


def build_lifecycle_service_bundle(
    *,
    deps: OrchestratorLifecycleDependencies,
    routing_config_provider: RoutingConfigProviderProtocol,
    task_registry: TaskRegistryProtocol,
    tool_name_extractor: Callable[[list[JSONValue]], list[str]],
    shutdown_event: asyncio.Event,
    health_check_config: dict[str, JSONValue],
    max_recovery_attempts: int,
) -> LifecycleServiceBundle:
    routing = OrchestratorLifecycleRoutingConfig(
        OrchestratorLifecycleRoutingConfigDependencies(
            orchestrator=deps.orchestrator,
            routing_config_provider=routing_config_provider,
            task_registry=task_registry,
        ),
    )
    circuit_breakers = OrchestratorLifecycleCircuitBreakers(
        OrchestratorLifecycleCircuitBreakersDependencies(
            orchestrator=deps.orchestrator,
            config=deps.config,
            shutdown_event=shutdown_event,
            state=deps.state_accessor,
        ),
    )
    runtime_state_side_effects = RuntimeStateSideEffects(
        RuntimeStateSideEffectsDependencies(
            orchestrator=deps.orchestrator,
            state=deps.state_accessor,
        ),
    )
    deps.authoritative_plugin_state_transitions.bind_runtime_state_side_effects(
        runtime_state_side_effects,
    )
    publisher: OrchestratorLifecyclePublisherProtocol = deps.authoritative_plugin_state_transitions
    watchers = OrchestratorLifecycleWatchers(
        OrchestratorLifecycleWatchersDependencies(
            orchestrator=deps.orchestrator,
            capacity=deps.capacity,
            state=deps.state_accessor,
            lifecycle_publisher=publisher,
            runtime_state_side_effects=runtime_state_side_effects,
        ),
    )
    shutdown = OrchestratorLifecycleShutdown(
        OrchestratorLifecycleShutdownDependencies(
            orchestrator=deps.orchestrator,
            capacity=deps.capacity,
            shutdown_event=shutdown_event,
            state=deps.state_accessor,
            lifecycle_publisher=publisher,
            task_registry=task_registry,
            health_check_config=health_check_config,
        ),
    )
    task_tracking = OrchestratorLifecycleTaskTracking(
        TaskTrackingDependencies(
            orchestrator=deps.orchestrator,
            capacity=deps.capacity,
            state=deps.state_accessor,
            shutdown_event=shutdown_event,
            lifecycle_publisher=publisher,
            tool_name_extractor=tool_name_extractor,
        ),
    )
    startup = OrchestratorLifecycleStartup(
        OrchestratorLifecycleStartupDependencies(
            orchestrator=deps.orchestrator,
            routing_config_provider=routing_config_provider,
            virtual_model_health=deps.virtual_model_health,
            virtual_model_rotation=deps.virtual_model_rotation,
            task_registry=task_registry,
            shutdown_event=shutdown_event,
            state=deps.state_accessor,
            lifecycle_publisher=publisher,
            shutdown=shutdown,
        ),
    )
    user_commands = OrchestratorLifecycleUserCommands(
        OrchestratorLifecycleUserCommandsDependencies(
            orchestrator=deps.orchestrator,
            task_registry=task_registry,
            watchers=watchers,
            lifecycle_publisher=publisher,
            circuit_breakers=circuit_breakers,
            shutdown=shutdown,
        ),
    )
    recovery = OrchestratorLifecycleRecovery(
        OrchestratorLifecycleRecoveryDependencies(
            orchestrator=deps.orchestrator,
            state=deps.state_accessor,
            lifecycle_publisher=publisher,
            circuit_breakers=circuit_breakers,
            shutdown=shutdown,
            max_recovery_attempts=max_recovery_attempts,
        ),
    )
    runtime_mutations = OrchestratorLifecycleRuntimeMutations(
        OrchestratorLifecycleRuntimeMutationsDependencies(
            orchestrator=deps.orchestrator,
            config_reload_handler=startup.execute_plugin_config_reload,
            config_reload_failure_publisher=startup.publish_config_reload_failure,
            stop_handler=shutdown.execute_stop_plugin,
            stop_command_handler=user_commands.execute_plugin_stop_command,
            disable_handler=user_commands.execute_plugin_disable_command,
            enable_handler=user_commands.execute_plugin_enable_command,
            clear_quarantine_handler=user_commands.execute_clear_quarantine,
            recovery_handler=recovery.execute_plugin_recovery,
        ),
    )
    startup.bind_runtime_mutations(runtime_mutations)
    watchers.bind_runtime_mutations(runtime_mutations)
    shutdown.bind_runtime_mutations(runtime_mutations)
    user_commands.bind_runtime_mutations(runtime_mutations)
    recovery.bind_runtime_mutations(runtime_mutations)
    return LifecycleServiceBundle(
        routing=routing,
        circuit_breakers=circuit_breakers,
        watchers=watchers,
        publisher=publisher,
        shutdown=shutdown,
        task_tracking=task_tracking,
        startup=startup,
        user_commands=user_commands,
        recovery=recovery,
        runtime_mutations=runtime_mutations,
    )
