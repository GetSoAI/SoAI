"""SoAI - Scheduler background task preparation [backend/orchestrator/scheduling/task_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.scheduling.actions import SchedulerAction, SchedulerActionType

if TYPE_CHECKING:
    from core.types.json import JSONDict

    type CoroutineFactory = Callable[[], Awaitable[None]]

__all__ = (
    "SchedulerTaskPreparation",
    "SchedulerTaskPreparationDependencies",
)


@dataclass(frozen=True, slots=True)
class SchedulerTaskPreparationDependencies:
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    dispatch_waiters: Callable[[str, str, JSONDict], Awaitable[None]]
    fail_waiters: Callable[[str, str], Awaitable[None]]
    reevaluate_routing_key: Callable[[str], Awaitable[None]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SchedulerTaskPreparationDependencies",
            dispatch_waiters=self.dispatch_waiters,
            fail_waiters=self.fail_waiters,
            lifecycle=self.lifecycle,
            reevaluate_routing_key=self.reevaluate_routing_key,
        )


class SchedulerTaskPreparation:
    def __init__(self, deps: SchedulerTaskPreparationDependencies) -> None:
        self._deps = deps

    def prepare(self, action: SchedulerAction) -> tuple[str, CoroutineFactory]:
        victim_plugin = action.victim_plugin
        if action.action_type == SchedulerActionType.EVICT_AND_START and victim_plugin is None:
            raise StateError(
                f"SchedulerAction missing victim_plugin for eviction for task [{action.task.task_id}].",
            )
        match action.action_type:
            case SchedulerActionType.DISPATCH:
                pending_key = action.pending_key or action.universal_id
                plugin_name = action.plugin_name
                model_info = action.model_info

                def dispatch_factory() -> Awaitable[None]:
                    return self._deps.dispatch_waiters(pending_key, plugin_name, model_info)

                return (
                    f"Dispatching waiters for ready model {action.universal_id}.",
                    dispatch_factory,
                )
            case SchedulerActionType.RELOAD:
                plugin_name = action.plugin_name

                async def _reload() -> None:
                    await self._deps.lifecycle.shutdown.stop_plugin(
                        plugin_name,
                        reason="Scheduled for parameter reload",
                    )

                return (
                    f"Scheduling a reload for plugin '{plugin_name}' for model {action.universal_id}.",
                    _reload,
                )
            case SchedulerActionType.START:
                task = action.task
                plugin_name = action.plugin_name
                model_info = action.model_info
                pending_key = action.pending_key or action.universal_id

                async def _start() -> None:
                    result = await self._deps.lifecycle.model_loading.start_plugin_and_load_model(
                        task,
                        plugin_name,
                        model_info,
                    )
                    if result.terminal_failure:
                        await self._deps.fail_waiters(
                            pending_key,
                            result.message
                            or f"Model '{action.universal_id}' failed to load on plugin '{plugin_name}'.",
                        )
                        return
                    if not result.loaded:
                        return
                    await uncancel_then_cleanup(
                        self._deps.reevaluate_routing_key(pending_key),
                    )

                return (f"Starting plugin '{plugin_name}' for model {action.universal_id}.", _start)
            case SchedulerActionType.EVICT_AND_START:
                if victim_plugin is None:
                    raise StateError(
                        f"SchedulerAction missing victim_plugin for eviction for task [{action.task.task_id}].",
                    )
                victim_name = victim_plugin
                plugin_name = action.plugin_name

                async def _evict() -> None:
                    await self._deps.lifecycle.shutdown.stop_plugin(
                        victim_name,
                        reason="Scheduled for eviction",
                    )

                return (
                    f"At capacity. Evicting '{victim_name}' to make room for '{plugin_name}'.",
                    _evict,
                )
