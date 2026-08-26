"""SoAI - Provider-backed scheduling readiness helpers [backend/orchestrator/scheduling/provider_backed_readiness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.models.provider_backing import is_provider_backed_model
from core.state.provider_backed_availability import (
    PROVIDER_BACKED_IGNORED_PLUGIN_STATES,
)
from orchestrator.scheduling.plugin_readiness_gates import (
    resolve_plugin_readiness_state,
)

if TYPE_CHECKING:
    from core.models.protocols import ModelInformationServiceProtocol
    from core.tasks.task import Task
    from orchestrator.scheduling.dispatching_dependencies import (
        SchedulerDispatchingDependencies,
    )
    from orchestrator.scheduling.internal_protocols import (
        PluginQueueDispatcherDependenciesProtocol,
    )
    from orchestrator.scheduling.plugin_readiness import PluginReadiness

__all__ = (
    "get_provider_aware_blocking_states",
    "get_provider_aware_ready_states",
    "resolve_provider_aware_plugin_readiness_state",
    "resolve_provider_aware_plugin_readiness_state_for_dispatch",
    "task_targets_provider_backed_model",
)


def get_provider_aware_ready_states(ready_states: set[str], provider_backed: bool) -> set[str]:
    if not provider_backed:
        return ready_states
    return ready_states | set(PROVIDER_BACKED_IGNORED_PLUGIN_STATES)


def get_provider_aware_blocking_states(
    states: set[str] | frozenset[str],
    provider_backed: bool,
) -> set[str] | frozenset[str]:
    if not provider_backed:
        return states
    return set(states) - set(PROVIDER_BACKED_IGNORED_PLUGIN_STATES)


async def task_targets_provider_backed_model(
    model_information_service: ModelInformationServiceProtocol,
    task: Task,
) -> bool:
    context = task.orchestration_context
    if context is None or not context.execution_universal_ids:
        return False
    model_info = await model_information_service.model_get_info(context.execution_universal_ids[0])
    return bool(model_info and is_provider_backed_model(model_info))


async def resolve_provider_aware_plugin_readiness_state(
    *,
    plugin_name: str,
    get_plugin_status: Callable[[str], Awaitable[str]],
    ready_states: set[str],
    unavailable_states: set[str] | frozenset[str],
    model_information_service: ModelInformationServiceProtocol,
    task: Task,
) -> tuple[str, PluginReadiness]:
    provider_backed = await task_targets_provider_backed_model(model_information_service, task)
    return await resolve_plugin_readiness_state(
        plugin_name=plugin_name,
        get_plugin_status=get_plugin_status,
        ready_states=get_provider_aware_ready_states(ready_states, provider_backed),
        unavailable_states=get_provider_aware_blocking_states(unavailable_states, provider_backed),
    )


async def resolve_provider_aware_plugin_readiness_state_for_dispatch(
    *,
    plugin_name: str,
    deps: SchedulerDispatchingDependencies | PluginQueueDispatcherDependenciesProtocol,
    unavailable_states: set[str] | frozenset[str],
    task: Task,
) -> tuple[str, PluginReadiness]:
    return await resolve_provider_aware_plugin_readiness_state(
        plugin_name=plugin_name,
        get_plugin_status=deps.state_aggregator.get_plugin_status,
        ready_states=deps.dispatch_ready_states,
        unavailable_states=unavailable_states,
        model_information_service=deps.model_information_service,
        task=task,
    )
