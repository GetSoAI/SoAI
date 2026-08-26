"""SoAI - Shared authoritative plugin state transition service [backend/app/background/authoritative_plugin_state/transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from app.background.authoritative_plugin_state.waiters import (
    AuthoritativePluginStateWaiters,
)
from core.concurrency.deadlines import wait_for_hard_deadline
from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.database.protocols import DatabaseCoreProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import ServiceUnavailableError
from core.events.authoritative_state_encoding import (
    encode_authoritative_plugin_state_event,
)
from core.events.publication_errors import PublicationDeadlineExceededError
from core.events.types_plugins import (
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
)
from core.runtime.request_context import RequestContext
from core.state.protocols import (
    AuthoritativePluginStateTransitionReceipt,
    StateAggregatorProtocol,
)
from core.state.protocols_publication import RuntimeStatePublicationSideEffectsProtocol
from core.state.state_names import (
    ORCHESTRATOR_STATE_NAMES,
    PLUGIN_STATE_NAMES,
    PLUGIN_STATE_STOPPED,
)
from core.state.state_transition_graph import get_valid_state_transitions
from core.types.json import JSONDict
from database.repositories.plugins.authoritative_state_outbox import (
    sync_record_authoritative_plugin_state_transition,
)

if TYPE_CHECKING:
    from core.state.state_names import PluginRuntimeStateName

__all__ = (
    "AuthoritativePluginStateTransitions",
    "AuthoritativePluginStateTransitionsDependencies",
    "RecordedAuthoritativePluginStateTransitionReceipt",
)

OPERATION_BEGIN_INSTALLATION_TRANSITION = (
    "authoritative_plugin_state_transitions.begin_installation_transition"
)


@dataclass(frozen=True, slots=True)
class AuthoritativePluginStateTransitionsDependencies:
    database_core: DatabaseCoreProtocol
    state_aggregator: StateAggregatorProtocol
    waiters: AuthoritativePluginStateWaiters

    def __post_init__(self) -> None:
        require_dependencies(
            owner="AuthoritativePluginStateTransitionsDependencies",
            database_core=self.database_core,
            state_aggregator=self.state_aggregator,
            waiters=self.waiters,
        )


@dataclass(frozen=True, slots=True)
class RecordedAuthoritativePluginStateTransitionReceipt(AuthoritativePluginStateTransitionReceipt):
    event: PluginInstallationStateChangedEvent | PluginRuntimeStateChangedEvent
    completion_waiter: asyncio.Future[None]

    @override
    async def wait_for_completion(self, deadline_monotonic: float) -> None:
        try:
            await wait_for_hard_deadline(
                deadline_monotonic,
                lambda remaining: asyncio.wait_for(
                    asyncio.shield(self.completion_waiter),
                    timeout=remaining,
                ),
            )
        except TimeoutError as exception:
            raise PublicationDeadlineExceededError(
                (
                    f"Timed out waiting for authoritative plugin state publication for "
                    f"'{self.event.plugin_name}'."
                ),
                operation="authoritative_plugin_state_transitions.wait_for_completion",
                details={
                    "event_id": self.event.event_id,
                    "event_type": type(self.event).__name__,
                    "plugin_name": self.event.plugin_name,
                },
                cause=exception,
            ) from exception


class AuthoritativePluginStateTransitions:
    def __init__(self, deps: AuthoritativePluginStateTransitionsDependencies) -> None:
        self._deps = deps
        self._runtime_state_transition_locks: TTLAsyncLockRegistry[str] = TTLAsyncLockRegistry(
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=7200.0,
                max_size=500,
                cleanup_interval_seconds=600.0,
            ),
        )
        self._runtime_state_side_effects: RuntimeStatePublicationSideEffectsProtocol | None = None

    def bind_runtime_state_side_effects(
        self,
        runtime_state_side_effects: RuntimeStatePublicationSideEffectsProtocol,
    ) -> None:
        self._runtime_state_side_effects = runtime_state_side_effects

    async def publish_runtime_state_change(
        self,
        plugin_name: str,
        new_state: PluginRuntimeStateName,
        reason: str,
        *,
        details: JSONDict | None = None,
        expected_previous_state: PluginRuntimeStateName | None = None,
        prioritize_for_eviction: bool = False,
    ) -> AuthoritativePluginStateTransitionReceipt | None:
        runtime_details = dict(details) if details is not None else {}
        if prioritize_for_eviction:
            runtime_details["prioritize_for_eviction"] = True
        return await self.begin_runtime_transition(
            plugin_name,
            new_state,
            reason,
            details=runtime_details,
            expected_previous_state=expected_previous_state,
        )

    async def begin_runtime_transition(
        self,
        plugin_name: str,
        new_state: PluginRuntimeStateName,
        reason: str,
        *,
        context: RequestContext | None = None,
        details: JSONDict | None = None,
        expected_previous_state: PluginRuntimeStateName | None = None,
    ) -> AuthoritativePluginStateTransitionReceipt | None:
        async with self._runtime_state_transition_locks.lock(plugin_name):
            runtime_state_side_effects = self._runtime_state_side_effects
            if runtime_state_side_effects is None:
                raise ServiceUnavailableError(
                    "Runtime state side effects must be bound before runtime publication.",
                    operation="authoritative_plugin_state_transitions.begin_runtime_transition",
                )
            previous_state = await self._deps.state_aggregator.get_plugin_status(plugin_name)
            if expected_previous_state is not None and previous_state != expected_previous_state:
                return None
            normalized_details = dict(details) if details is not None else {}
            if previous_state == new_state:
                if not normalized_details:
                    return None
                all_plugin_states = await self._deps.state_aggregator.get_all_plugin_states()
                current_plugin_state = all_plugin_states.get(plugin_name) or {}
                current_details_value = current_plugin_state.get("details")
                current_details = (
                    dict(current_details_value) if isinstance(current_details_value, dict) else {}
                )
                desired_details = dict(current_details)
                for key, value in normalized_details.items():
                    desired_details[key] = value
                if new_state == PLUGIN_STATE_STOPPED and desired_details:
                    desired_details = {}
                if desired_details == current_details:
                    return None
                event = PluginRuntimeStateChangedEvent(
                    plugin_name=plugin_name,
                    previous_state=previous_state,
                    new_state=new_state,
                    reason=reason,
                    details=normalized_details,
                    context=context,
                )
                receipt = await self._record_transition(event)
                await runtime_state_side_effects.apply_local_publication(event)
                return receipt
            valid_transitions = get_valid_state_transitions(previous_state)
            if new_state not in valid_transitions:
                raise ServiceUnavailableError(
                    "Invalid authoritative runtime state transition.",
                    operation="authoritative_plugin_state_transitions.begin_runtime_transition",
                    details={
                        "plugin_name": plugin_name,
                        "previous_state": previous_state,
                        "new_state": new_state,
                    },
                )
            event = PluginRuntimeStateChangedEvent(
                plugin_name=plugin_name,
                previous_state=previous_state,
                new_state=new_state,
                reason=reason,
                details=normalized_details,
                context=context,
            )
            receipt = await self._record_transition(event)
            await runtime_state_side_effects.apply_local_publication(event)
            return receipt

    async def begin_installation_transition(
        self,
        plugin_name: str,
        new_state: PluginRuntimeStateName,
        reason: str,
        *,
        context: RequestContext | None = None,
    ) -> AuthoritativePluginStateTransitionReceipt | None:
        async with self._runtime_state_transition_locks.lock(plugin_name):
            previous_state = await self._deps.state_aggregator.get_plugin_status(plugin_name)
            if previous_state == new_state:
                return None
            if new_state not in PLUGIN_STATE_NAMES:
                raise ServiceUnavailableError(
                    "Installation transitions must use plugin state names.",
                    operation=OPERATION_BEGIN_INSTALLATION_TRANSITION,
                    details={
                        "plugin_name": plugin_name,
                        "previous_state": previous_state,
                        "new_state": new_state,
                    },
                )
            previous_is_orchestrator_only = (
                previous_state in ORCHESTRATOR_STATE_NAMES
                and previous_state not in PLUGIN_STATE_NAMES
            )
            if not previous_is_orchestrator_only:
                valid_transitions = get_valid_state_transitions(previous_state)
                if new_state not in valid_transitions:
                    raise ServiceUnavailableError(
                        "Invalid authoritative installation state transition.",
                        operation=OPERATION_BEGIN_INSTALLATION_TRANSITION,
                        details={
                            "plugin_name": plugin_name,
                            "previous_state": previous_state,
                            "new_state": new_state,
                        },
                    )
            event = PluginInstallationStateChangedEvent(
                plugin_name=plugin_name,
                previous_state=previous_state,
                new_state=new_state,
                reason=reason,
                context=context,
            )
            return await self._record_transition(event)

    async def _record_transition(
        self,
        event: PluginInstallationStateChangedEvent | PluginRuntimeStateChangedEvent,
    ) -> AuthoritativePluginStateTransitionReceipt:
        payload_json = encode_authoritative_plugin_state_event(event)
        completion_waiter = await self._deps.waiters.create(event.event_id)
        transition_recorded = False
        try:
            await self._deps.database_core.writer.queue_write_operation(
                sync_record_authoritative_plugin_state_transition,
                event.plugin_name,
                event.new_state,
                event.event_id,
                type(event).__name__,
                payload_json,
                int(event.timestamp * 1000.0),
            )
            transition_recorded = True
        finally:
            if not transition_recorded:
                await asyncio.shield(self._deps.waiters.discard(event.event_id))
        await self._deps.state_aggregator.apply_authoritative_plugin_state_change(event)
        return RecordedAuthoritativePluginStateTransitionReceipt(
            event=event,
            completion_waiter=completion_waiter,
        )
